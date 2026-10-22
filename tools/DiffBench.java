import io.github.linkfgfgui.minimalbackup.engine.Block;
import io.github.linkfgfgui.minimalbackup.engine.Codec;
import io.github.linkfgfgui.minimalbackup.engine.EngineSettings;
import io.github.linkfgfgui.minimalbackup.engine.Xxh64;
import io.github.linkfgfgui.minimalbackup.engine.anvil.AnvilRegion;
import io.github.linkfgfgui.minimalbackup.engine.nbt.NbtCanon;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.PrintWriter;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Stream;
import java.util.zip.GZIPInputStream;
import java.util.zip.InflaterInputStream;

/**
 * Replays a sequence of progressive full world saves through the project's own storage engine.
 *
 * <p>Input is a TSV manifest, one snapshot per line:
 * {@code label<TAB>worldDir[;worldDir...]<TAB>sourceBytes<TAB>prepareCommand}. Snapshots must be
 * ordered oldest first. A snapshot may combine several world roots (for servers that keep the
 * nether and the end as sibling directories); their targets are namespaced by directory name. The
 * optional prepare command runs before the snapshot is scanned and is not charged to the scan
 * time; this is how a git history is materialised one commit at a time. For every
 * snapshot the runner reconstructs the engine's targets (every non-empty chunk in
 * region/entities/poi .mca files and every tracked .dat file), canonicalises NBT with
 * {@link NbtCanon}, and applies the checkpoint policy: first snapshot = FULL baseline, a changed
 * target = DELTA against the previous visible block, a new target = FULL plus an ABSENT marker,
 * a deleted target = ABSENT, an unchanged target = nothing.
 *
 * <p>Every block is decompressed and byte-compared after writing ({@code roundtrip_fail}).
 * Output CSVs describe per-version totals, per-family split, per-target changes and per-file
 * activity. Nothing outside {@code outDir} is written.
 *
 * <pre>
 * usage: DiffBench &lt;manifest.tsv&gt; &lt;outDir&gt; [level] [long]
 * </pre>
 */
public final class DiffBench {
    private static final int HEADER = Block.HEADER_SIZE;
    private static final Pattern REGION = Pattern.compile("r\\.(-?\\d+)\\.(-?\\d+)\\.mca$");
    private static final int DEFAULT_LEVEL = Integer.getInteger("bench.level", 3);
    private static int level = DEFAULT_LEVEL;
    private static EngineSettings settings;
    /** v1 .zpack cache entry size; v2 is one varint per block (see README). */
    private static final int CACHE_ENTRY_BYTES_V1 = 30;
    private static long targetsSeen = 0L;
    private static long canonicalSeen = 0L;

    private DiffBench() {
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 2) {
            System.err.println("usage: DiffBench <manifest.tsv> <outDir> [level] [long]");
            System.exit(2);
        }
        Path manifest = Paths.get(args[0]);
        Path outDir = Paths.get(args[1]);
        level = args.length > 2 ? Integer.parseInt(args[2]) : DEFAULT_LEVEL;
        boolean longMode = args.length > 3 ? Boolean.parseBoolean(args[3])
                : Boolean.getBoolean("bench.long");
        Files.createDirectories(outDir);
        settings = new EngineSettings(level, longMode, EngineSettings.MAX_ZSTD_LONG_WINDOW_LOG,
                -1, true);

        List<Entry> versions = readManifest(manifest);
        if (versions.isEmpty()) {
            System.err.println("empty manifest: " + manifest);
            System.exit(2);
        }

        Path versionsCsv = outDir.resolve("versions.csv");
        Path familiesCsv = outDir.resolve("families.csv");
        Path changesCsv = outDir.resolve("changes.csv");
        Path regionsCsv = outDir.resolve("regions.csv");
        Path skippedCsv = outDir.resolve("skipped.csv");
        Map<String, State> previous = null;
        long cumulativeMin = 0L;
        long cumulativeActual = 0L;
        long cumulativeSource = 0L;

        try (PrintWriter versionsOut = new PrintWriter(Files.newBufferedWriter(versionsCsv,
                StandardCharsets.UTF_8));
             PrintWriter familiesOut = new PrintWriter(Files.newBufferedWriter(familiesCsv,
                     StandardCharsets.UTF_8));
             PrintWriter changesOut = new PrintWriter(Files.newBufferedWriter(changesCsv,
                     StandardCharsets.UTF_8));
             PrintWriter regionsOut = new PrintWriter(Files.newBufferedWriter(regionsCsv,
                     StandardCharsets.UTF_8));
             PrintWriter skippedOut = new PrintWriter(Files.newBufferedWriter(skippedCsv,
                     StandardCharsets.UTF_8))) {
            versionsOut.println("version,baseline,source_bytes,world_bytes,files_total,"
                    + "files_untracked,untracked_bytes,targets,chunks,files,new,changed,deleted,"
                    + "unchanged,canon_unchanged,logical_bytes,full_payload,full_total,"
                    + "delta_payload,new_full_payload,incr_payload,incr_headers,incr_total,"
                    + "incr_vs_full_pct,cumulative_min,cumulative_source,scan_ms,canon_ms,full_ms,"
                    + "delta_ms,total_ms,prepare_ms,roundtrip_fail,codec,region_records," + "skipped_targets,"
                    + "zpacks,new_zpacks,cache_bytes,actual_full_total,actual_incr_total,"
                    + "actual_cumulative_min,zstd_level,zstd_long");
            familiesOut.println("version,family,targets,new,changed,deleted,unchanged,"
                    + "logical_bytes,full_payload,full_total,delta_payload,new_full_payload,"
                    + "incr_total,incr_vs_full_pct");
            changesOut.println("version,key,family,old_len,new_len,full_bytes,delta_bytes,mode");
            regionsOut.println("version,file,family,new,changed,deleted,delta_bytes,"
                    + "new_full_bytes,incr_bytes");
            skippedOut.println("version,key,reason");

            boolean first = true;
            for (Entry entry : versions) {
                long prepareMs = 0L;
                if (entry.prepare() != null) {
                    long p0 = System.nanoTime();
                    runPrepare(entry, outDir);
                    prepareMs = (System.nanoTime() - p0) / 1_000_000L;
                }
                long t0 = System.nanoTime();
                VersionResult result = scanAndDiff(entry.label(), entry.worlds(), previous,
                        entry.changes(), changesOut, skippedOut, first);
                result.totalMs = (System.nanoTime() - t0) / 1_000_000L;

                cumulativeSource += entry.sourceBytes();
                cumulativeMin += result.incrTotal;
                cumulativeActual += result.actualIncrTotal;

                StringBuilder row = new StringBuilder(256);
                row.append(entry.label()).append(',').append(first).append(',')
                        .append(entry.sourceBytes()).append(',').append(result.worldBytes).append(',')
                        .append(result.filesTotal).append(',').append(result.filesUntracked)
                        .append(',').append(result.untrackedBytes).append(',')
                        .append(result.targets).append(',').append(result.chunks).append(',')
                        .append(result.files).append(',').append(result.newTargets).append(',')
                        .append(result.changed).append(',').append(result.deleted).append(',')
                        .append(result.unchanged).append(',').append(result.canonUnchanged)
                        .append(',').append(result.logicalBytes).append(',')
                        .append(result.fullPayload).append(',').append(result.fullTotal).append(',')
                        .append(result.deltaPayload).append(',').append(result.newFullPayload)
                        .append(',').append(result.incrPayload).append(',')
                        .append(result.incrHeaders).append(',').append(result.incrTotal).append(',')
                        .append(String.format(Locale.ROOT, "%.4f",
                                result.fullTotal == 0 ? 0.0
                                        : 100.0 * result.incrTotal / result.fullTotal))
                        .append(',').append(cumulativeMin).append(',').append(cumulativeSource)
                        .append(',').append(result.scanMs).append(',').append(result.canonMs)
                        .append(',').append(result.fullMs).append(',').append(result.deltaMs)
                        .append(',').append(result.totalMs).append(',').append(prepareMs)
                        .append(',').append(result.roundTripFail).append(',').append(Codec.id())
                        .append(',').append(result.regionRecords).append(',')
                        .append(result.skippedTargets).append(',').append(result.zpacks)
                        .append(',').append(result.newZpacks).append(',')
                        .append(result.cacheBytes).append(',').append(result.actualFullTotal)
                        .append(',').append(result.actualIncrTotal).append(',')
                        .append(cumulativeActual).append(',').append(level).append(',')
                        .append(longMode);
                versionsOut.println(row);
                versionsOut.flush();

                writeFamily(familiesOut, entry.label(), "chunk", result.chunkStats);
                writeFamily(familiesOut, entry.label(), "file", result.fileStats);
                for (Map.Entry<String, RegionStats> region : result.regions.entrySet()) {
                    RegionStats s = region.getValue();
                    regionsOut.printf(Locale.ROOT, "%s,%s,%s,%d,%d,%d,%d,%d,%d%n",
                            entry.label(), csv(region.getKey()), s.family, s.newTargets,
                            s.changed, s.deleted, s.deltaBytes, s.newFullBytes, s.incrBytes);
                }

                previous = result.current;
                first = false;
                System.out.printf(Locale.ROOT,
                        "[%s] targets=%d new=%d changed=%d deleted=%d logical=%.1fMB "
                                + "full=%.1fMB incr=%.1fMB (%.2f%%) vault=%.1fMB time=%dms%n",
                        entry.label(), result.targets, result.newTargets, result.changed,
                        result.deleted, result.logicalBytes / 1e6, result.actualFullTotal / 1e6,
                        result.actualIncrTotal / 1e6,
                        result.actualFullTotal == 0 ? 0.0
                                : 100.0 * result.actualIncrTotal / result.actualFullTotal,
                        cumulativeActual / 1e6, result.totalMs);
                if (prepareMs > 0) {
                    System.out.printf(Locale.ROOT, "  prepare=%dms%n", prepareMs);
                }
                System.out.flush();
            }
        }
        System.out.println("wrote " + versionsCsv + ", " + familiesCsv + ", " + changesCsv
                + ", " + regionsCsv + ", " + skippedCsv);
    }

    private record World(Path path, String prefix) {
    }

    private record Entry(String label, List<World> worlds, long sourceBytes, String prepare,
                         Path changes) {
    }

    private static List<Entry> readManifest(Path manifest) throws IOException {
        List<Entry> entries = new ArrayList<>();
        for (String line : Files.readAllLines(manifest, StandardCharsets.UTF_8)) {
            String trimmed = line.strip();
            if (trimmed.isEmpty() || trimmed.startsWith("#")) {
                continue;
            }
            String[] parts = trimmed.split("\t", -1);
            if (parts.length < 2) {
                throw new IOException("bad manifest line (want label<TAB>worldDir<TAB>bytes): "
                        + line);
            }
            String[] roots = parts[1].split(";");
            boolean multi = roots.length > 1;
            Set<String> used = new HashSet<>();
            List<World> worlds = new ArrayList<>();
            for (String root : roots) {
                Path path = Paths.get(root.trim());
                String prefix = "";
                if (multi) {
                    Path name = path.getFileName();
                    String base = name == null ? "root" : name.toString();
                    String candidate = base;
                    for (int i = 2; !used.add(candidate); i++) {
                        candidate = base + "-" + i;
                    }
                    prefix = candidate + "/";
                }
                worlds.add(new World(path, prefix));
            }
            long bytes = parts.length > 2 && !parts[2].isBlank()
                    ? Long.parseLong(parts[2].trim()) : 0L;
            String prepare = parts.length > 3 && !parts[3].isBlank() ? parts[3].trim() : null;
            Path changes = parts.length > 4 && !parts[4].isBlank()
                    ? Paths.get(parts[4].trim()) : null;
            entries.add(new Entry(parts[0].trim(), worlds, bytes, prepare, changes));
        }
        return entries;
    }

    private static void runPrepare(Entry entry, Path outDir) throws IOException {
        ProcessBuilder builder = new ProcessBuilder("/bin/sh", "-c", entry.prepare());
        builder.directory(outDir.toFile());
        builder.redirectErrorStream(true);
        Process process = builder.start();
        byte[] output;
        try (InputStream in = process.getInputStream()) {
            output = readAll(in);
        }
        int code;
        try {
            code = process.waitFor();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IOException("prepare interrupted for " + entry.label(), e);
        }
        if (code != 0) {
            throw new IOException("prepare failed (" + code + ") for " + entry.label() + ":\n"
                    + new String(output, StandardCharsets.UTF_8));
        }
    }

    private static void writeFamily(PrintWriter out, String version, String family, FamilyStats s) {
        out.printf(Locale.ROOT, "%s,%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%.4f%n",
                version, family, s.targets, s.newTargets, s.changed, s.deleted, s.unchanged,
                s.logicalBytes, s.fullPayload, s.fullTotal, s.deltaPayload, s.newFullPayload,
                s.incrTotal,
                s.fullTotal == 0 ? 0.0 : 100.0 * s.incrTotal / s.fullTotal);
    }

    private static final class State {
        /** Aligned canonical bytes as they were written; this is the delta base. */
        final byte[] stored;
        /** Canonical length before alignment, for reporting only. */
        final int canonicalLen;
        final long rawHash;
        final long canonHash;
        final int type;
        final int fullLen;

        State(byte[] stored, int canonicalLen, long rawHash, long canonHash, int type,
              int fullLen) {
            this.stored = stored;
            this.canonicalLen = canonicalLen;
            this.rawHash = rawHash;
            this.canonHash = canonHash;
            this.type = type;
            this.fullLen = fullLen;
        }
    }

    private static final class FamilyStats {
        long targets;
        long newTargets;
        long changed;
        long deleted;
        long unchanged;
        long logicalBytes;
        long fullPayload;
        long fullTotal;
        long deltaPayload;
        long newFullPayload;
        long incrTotal;
    }

    private static final class RegionStats {
        final String family;
        long newTargets;
        long changed;
        long deleted;
        long deltaBytes;
        long newFullBytes;
        long incrBytes;

        RegionStats(String family) {
            this.family = family;
        }
    }

    private static final class VersionResult {
        Map<String, State> current = new HashMap<>();
        Map<String, RegionStats> regions = new TreeMap<>();
        long targets;
        long chunks;
        long files;
        long newTargets;
        long changed;
        long deleted;
        long unchanged;
        long canonUnchanged;
        long logicalBytes;
        long fullPayload;
        long fullTotal;
        long deltaPayload;
        long newFullPayload;
        long incrPayload;
        long incrHeaders;
        long incrTotal;
        long worldBytes;
        long filesTotal;
        long filesUntracked;
        long untrackedBytes;
        long scanMs;
        long canonMs;
        long fullMs;
        long deltaMs;
        long totalMs;
        long roundTripFail;
        long regionRecords;
        long skippedTargets;
        long skipExternal;
        long skipInvalid;
        long skipRead;
        long skipUnsupported;
        long skipNonNbt;
        long skipDatGzip;
        long skipDatNonNbt;
        long zpacks;
        long newZpacks;
        long cacheBytes;
        long actualFullTotal;
        long actualIncrTotal;
        final FamilyStats chunkStats = new FamilyStats();
        final FamilyStats fileStats = new FamilyStats();
    }

    private static VersionResult scanAndDiff(String label, List<World> worlds,
                                             Map<String, State> previous, Path changeFile,
                                             PrintWriter changes, PrintWriter skipped,
                                             boolean first) throws IOException {
        VersionResult r = new VersionResult();
        boolean incremental = !first && previous != null && changeFile != null
                && Files.isRegularFile(changeFile);
        if (incremental) {
            r.current.putAll(previous);
        }
        long tStart = System.nanoTime();
        for (World world : worlds) {
            if (!Files.isDirectory(world.path())) {
                continue;
            }
            List<Path> paths = new ArrayList<>();
            try (Stream<Path> walk = Files.walk(world.path())) {
                walk.filter(Files::isRegularFile).forEach(paths::add);
            }
            paths.sort(Comparator.comparing(p -> world.path().relativize(p).toString()));

            for (Path path : paths) {
                String local = world.path().relativize(path).toString().replace('\\', '/');
                String rel = world.prefix() + local;
                String name = path.getFileName().toString();
                long size = Files.size(path);
                r.worldBytes += size;
                r.filesTotal++;
                if (name.endsWith(".mca")) {
                    if (!incremental) {
                        scanRegion(label, path, rel, previous, r, changes, skipped, first);
                    }
                } else if (isTrackedDat(local)) {
                    if (!incremental) {
                        scanDat(label, path, rel, previous, r, changes, skipped, first);
                    }
                } else {
                    r.filesUntracked++;
                    r.untrackedBytes += size;
                }
            }
        }
        if (incremental) {
            applyChanges(label, worlds, changeFile, previous, r, changes, skipped);
        }
        r.scanMs = (System.nanoTime() - tStart) / 1_000_000L;

        // Targets that disappeared since the previous version.
        if (previous != null) {
            for (Map.Entry<String, State> e : previous.entrySet()) {
                if (!r.current.containsKey(e.getKey())) {
                    State old = e.getValue();
                    r.deleted++;
                    r.incrHeaders += HEADER;
                    r.incrTotal += HEADER;
                    FamilyStats fs = old.type == Block.TYPE_CHUNK ? r.chunkStats : r.fileStats;
                    fs.deleted++;
                    fs.incrTotal += HEADER;
                    String file = e.getKey().substring(0, e.getKey().lastIndexOf('#'));
                    RegionStats rs = region(r, file, old.type);
                    rs.deleted++;
                    rs.incrBytes += HEADER;
                    changes.printf("%s,%s,%s,%d,0,0,0,ABSENT%n", label, csv(e.getKey()),
                            family(old.type), old.canonicalLen);
                }
            }
        }

        r.targets = r.current.size();
        // Totals are derived from the visible state, not from what happened to be scanned this
        // time. Incremental scans reuse this path with most targets carried over.
        r.logicalBytes = 0L;
        r.fullPayload = 0L;
        r.chunks = 0L;
        r.files = 0L;
        r.chunkStats.targets = 0L;
        r.fileStats.targets = 0L;
        r.chunkStats.logicalBytes = 0L;
        r.fileStats.logicalBytes = 0L;
        r.chunkStats.fullPayload = 0L;
        r.fileStats.fullPayload = 0L;
        for (State state : r.current.values()) {
            r.logicalBytes += state.canonicalLen;
            r.fullPayload += state.fullLen;
            FamilyStats fs = family(r, state.type);
            fs.targets++;
            fs.logicalBytes += state.canonicalLen;
            fs.fullPayload += state.fullLen;
            if (state.type == Block.TYPE_CHUNK) {
                r.chunks++;
            } else {
                r.files++;
            }
        }
        r.unchanged = first ? 0L : r.targets - r.newTargets - r.changed;
        r.chunkStats.unchanged = first ? 0L
                : r.chunkStats.targets - r.chunkStats.newTargets - r.chunkStats.changed;
        r.fileStats.unchanged = first ? 0L
                : r.fileStats.targets - r.fileStats.newTargets - r.fileStats.changed;
        r.fullTotal = r.fullPayload + (long) HEADER * r.targets;
        if (first) {
            // The baseline writes every target as FULL, so all of it is "new" storage.
            r.newFullPayload = r.fullPayload;
        }
        if (first) {
            r.incrPayload = r.fullPayload;
            r.incrHeaders = (long) HEADER * r.targets;
            r.incrTotal = r.fullTotal;
        } else {
            r.incrTotal = r.incrPayload + r.incrHeaders;
        }
        Set<String> currentZpacks = new HashSet<>();
        for (String key : r.current.keySet()) {
            currentZpacks.add(key.substring(0, key.lastIndexOf('#')));
        }
        r.zpacks = currentZpacks.size();
        if (previous != null) {
            Set<String> previousZpacks = new HashSet<>();
            for (String key : previous.keySet()) {
                previousZpacks.add(key.substring(0, key.lastIndexOf('#')));
            }
            for (String zpack : currentZpacks) {
                if (!previousZpacks.contains(zpack)) {
                    r.newZpacks++;
                }
            }
        } else {
            r.newZpacks = r.zpacks;
        }
        long blocksAppended = first ? r.targets
                : r.changed + 2L * r.newTargets + r.deleted;
        r.cacheBytes = (long) CACHE_ENTRY_BYTES_V1 * blocksAppended + 28L * r.newZpacks;
        r.actualFullTotal = r.fullTotal + 30L * r.targets + 28L * r.zpacks;
        r.actualIncrTotal = r.incrTotal + r.cacheBytes;

        r.chunkStats.fullTotal = r.chunkStats.fullPayload + (long) HEADER * r.chunkStats.targets;
        r.fileStats.fullTotal = r.fileStats.fullPayload + (long) HEADER * r.fileStats.targets;
        if (first) {
            r.chunkStats.incrTotal = r.chunkStats.fullTotal;
            r.fileStats.incrTotal = r.fileStats.fullTotal;
            r.chunkStats.newFullPayload = r.chunkStats.fullPayload;
            r.fileStats.newFullPayload = r.fileStats.fullPayload;
        }
        return r;
    }

    private static void applyChanges(String label, List<World> worlds, Path changeFile,
                                     Map<String, State> previous, VersionResult r,
                                     PrintWriter changes, PrintWriter skipped) throws IOException {
        for (String line : Files.readAllLines(changeFile, StandardCharsets.UTF_8)) {
            if (line.isBlank() || line.startsWith("#")) {
                continue;
            }
            String[] parts = line.split("\t", 2);
            if (parts.length < 2) {
                continue;
            }
            String status = parts[0].trim();
            String keyPath = parts[1].trim();
            r.current.keySet().removeIf(key -> key.startsWith(keyPath + "#"));
            if (status.equals("D")) {
                continue;
            }
            for (World world : worlds) {
                if (!keyPath.startsWith(world.prefix())) {
                    continue;
                }
                String local = keyPath.substring(world.prefix().length());
                Path path = world.path().resolve(local);
                if (!Files.isRegularFile(path)) {
                    break;
                }
                String name = path.getFileName().toString();
                if (name.endsWith(".mca")) {
                    scanRegion(label, path, keyPath, previous, r, changes, skipped, false);
                } else if (isTrackedDat(local)) {
                    scanDat(label, path, keyPath, previous, r, changes, skipped, false);
                }
                break;
            }
        }
    }

    private static RegionStats region(VersionResult r, String file, int type) {
        return r.regions.computeIfAbsent(file, f -> new RegionStats(family(type)));
    }

    private static boolean isTrackedDat(String rel) {
        if (!rel.endsWith(".dat")) {
            return false;
        }
        String name = rel.substring(rel.lastIndexOf('/') + 1);
        if (name.equals("level.dat_old") || name.equals("session.lock")) {
            return false;
        }
        if (rel.equals("level.dat")) {
            return true;
        }
        if (rel.startsWith("playerdata/")) {
            return true;
        }
        for (String segment : rel.split("/")) {
            if (segment.equals("data")) {
                return true;
            }
        }
        return false;
    }

    private static int scanRegion(String label, Path path, String rel,
                                  Map<String, State> previous, VersionResult r,
                                  PrintWriter changes, PrintWriter skipped, boolean first)
            throws IOException {
        Matcher m = REGION.matcher(path.getFileName().toString());
        if (!m.find()) {
            return 0;
        }
        int regionX = Integer.parseInt(m.group(1));
        int regionZ = Integer.parseInt(m.group(2));
        int added = 0;
        try (FileChannel channel = FileChannel.open(path, StandardOpenOption.READ)) {
            long fileSize = channel.size();
            AnvilRegion region = AnvilRegion.parse(channel, fileSize);
            for (int i = 0; i < AnvilRegion.CHUNK_COUNT; i++) {
                if (!region.present(i)) {
                    continue;
                }
                r.regionRecords++;
                int chunkX = (regionX << 5) + (i & 31);
                int chunkZ = (regionZ << 5) + (i >> 5);
                String key = rel + "#" + AnvilRegion.chunkSubTarget(chunkX, chunkZ);
                AnvilRegion.Stored stored = region.stored(channel, i);
                if (stored == null) {
                    skip(r, skipped, label, key, "stored-null", 0);
                    continue;
                }
                if (!stored.valid()) {
                    skip(r, skipped, label, key, "invalid-record", 0);
                    continue;
                }
                if (stored.external()) {
                    skip(r, skipped, label, key, "external-mcc", 0);
                    continue;
                }
                byte[] record = readFully(channel, region.dataOffset(i) + 4L, stored.length());
                if (record == null || record.length < 1) {
                    skip(r, skipped, label, key, "read-fail", 0);
                    continue;
                }
                int compression = record[0] & 0xFF;
                byte[] compressed = Arrays.copyOfRange(record, 1, record.length);
                byte[] raw;
                try {
                    raw = decompress(compression, compressed);
                } catch (IOException e) {
                    skip(r, skipped, label, key, "compression-" + compression, 0);
                    continue;
                }
                if (!NbtCanon.looksLikeNbt(raw)) {
                    skip(r, skipped, label, key, "non-nbt", 0);
                    continue;
                }
                try {
                    if (processTarget(label, key, Block.TYPE_CHUNK, raw, previous, r, changes,
                            first)) {
                        added++;
                    }
                } catch (OutOfMemoryError e) {
                    System.err.printf(Locale.ROOT, "OOM target=%s raw=%.1fMB canon=%.1fMB%n",
                            key, raw.length / 1e6, canonicalSeen / 1e6);
                    throw e;
                }
            }
        }
        return added;
    }

    private static int scanDat(String label, Path path, String rel, Map<String, State> previous,
                               VersionResult r, PrintWriter changes, PrintWriter skipped,
                               boolean first) throws IOException {
        byte[] file = Files.readAllBytes(path);
        byte[] raw = file;
        if (file.length >= 2 && (file[0] & 0xFF) == 0x1F && (file[1] & 0xFF) == 0x8B) {
            try (InputStream in = new GZIPInputStream(new ByteArrayInputStream(file))) {
                raw = readAll(in);
            } catch (IOException e) {
                skip(r, skipped, label, rel + "#0", "dat-gzip", 0);
                return 0;
            }
        }
        if (!NbtCanon.looksLikeNbt(raw)) {
            skip(r, skipped, label, rel + "#0", "dat-non-nbt", 0);
            return 0;
        }
        String key = rel + "#0";
        return processTarget(label, key, Block.TYPE_FILE, raw, previous, r, changes, first) ? 1 : 0;
    }

    private static void skip(VersionResult r, PrintWriter out, String label, String key,
                             String reason, int ignored) {
        r.skippedTargets++;
        switch (reason) {
            case "stored-null" -> r.skipRead++;
            case "invalid-record" -> r.skipInvalid++;
            case "external-mcc" -> r.skipExternal++;
            case "dat-gzip" -> r.skipDatGzip++;
            case "dat-non-nbt" -> r.skipDatNonNbt++;
            case "non-nbt" -> r.skipNonNbt++;
            default -> r.skipUnsupported++;
        }
        out.println(label + "," + csv(key) + "," + reason);
    }

    private static boolean processTarget(String label, String key, int type, byte[] raw,
                                         Map<String, State> previous, VersionResult r,
                                         PrintWriter changes, boolean first) throws IOException {
        long t0 = System.nanoTime();
        long rawHash = Xxh64.hash(raw);
        State old = previous == null ? null : previous.get(key);
        if (old != null && old.rawHash == rawHash && old.type == type) {
            r.current.put(key, old);
            return true;
        }

        long tCanon = System.nanoTime();
        NbtCanon.Result canonical = NbtCanon.canonicalize(raw);
        byte[] cbytes = canonical.bytes();
        long canonHash = Xxh64.hash(cbytes);
        canonicalSeen += cbytes.length;
        if (++targetsSeen % 5000 == 0) {
            Runtime rt = Runtime.getRuntime();
            System.err.printf(Locale.ROOT,
                    "[mem] targets=%d canon=%.2fGB heapUsed=%.2fGB heapMax=%.2fGB%n",
                    targetsSeen, canonicalSeen / 1e9,
                    (rt.totalMemory() - rt.freeMemory()) / 1e9, rt.maxMemory() / 1e9);
        }
        r.canonMs += (System.nanoTime() - tCanon) / 1_000_000L;

        if (old != null && old.canonHash == canonHash && old.type == type) {
            r.current.put(key, new State(old.stored, cbytes.length, rawHash, canonHash, type,
                    old.fullLen));
            r.canonUnchanged++;
            return true;
        }

        long tFull = System.nanoTime();
        byte[] full = Codec.compressFull(cbytes, level, type);
        byte[] fullBack = Codec.decompress(full, null, cbytes.length, type);
        if (!Arrays.equals(fullBack, cbytes)) {
            r.roundTripFail++;
        }
        r.fullMs += (System.nanoTime() - tFull) / 1_000_000L;

        if (old == null) {
            r.current.put(key, new State(cbytes, cbytes.length, rawHash, canonHash, type,
                    full.length));
            FamilyStats fs = family(r, type);
            String file = key.substring(0, key.lastIndexOf('#'));
            RegionStats rs = region(r, file, type);
            rs.newTargets++;
            rs.newFullBytes += full.length;
            if (!first) {
                r.newTargets++;
                r.newFullPayload += full.length;
                r.incrPayload += full.length;
                r.incrHeaders += (long) HEADER * 2;
                fs.newTargets++;
                fs.newFullPayload += full.length;
                fs.incrTotal += full.length + (long) HEADER * 2;
                rs.incrBytes += full.length + (long) HEADER * 2;
                changes.printf("%s,%s,%s,0,%d,%d,0,FULL_NEW%n", label, csv(key),
                        family(type), cbytes.length, full.length);
            } else {
                rs.incrBytes += full.length + HEADER;
            }
            return true;
        }

        long tDelta = System.nanoTime();
        byte[] aligned = NbtCanon.alignCanonical(old.stored, canonical);
        byte[] delta = Codec.compressDelta(aligned, old.stored, settings, type);
        byte[] deltaBack = Codec.decompress(delta, old.stored, aligned.length, type);
        if (!Arrays.equals(deltaBack, aligned)) {
            r.roundTripFail++;
        }
        r.deltaMs += (System.nanoTime() - tDelta) / 1_000_000L;
        r.current.put(key, new State(aligned, cbytes.length, rawHash, canonHash, type,
                full.length));
        r.changed++;
        r.deltaPayload += delta.length;
        r.incrPayload += delta.length;
        r.incrHeaders += HEADER;
        FamilyStats fs = family(r, type);
        fs.changed++;
        fs.deltaPayload += delta.length;
        fs.incrTotal += delta.length + HEADER;
        String file = key.substring(0, key.lastIndexOf('#'));
        RegionStats rs = region(r, file, type);
        rs.changed++;
        rs.deltaBytes += delta.length;
        rs.incrBytes += delta.length + HEADER;
        changes.printf("%s,%s,%s,%d,%d,%d,%d,DELTA%n", label, csv(key), family(type),
                old.canonicalLen, cbytes.length, full.length, delta.length);
        return true;
    }

    private static void addUnchangedFamily(VersionResult r, int type, int logical, int fullLen) {
        FamilyStats fs = family(r, type);
        fs.unchanged++;
        fs.logicalBytes += logical;
        fs.fullPayload += fullLen;
    }

    private static FamilyStats family(VersionResult r, int type) {
        return type == Block.TYPE_CHUNK ? r.chunkStats : r.fileStats;
    }

    private static String family(int type) {
        return type == Block.TYPE_CHUNK ? "chunk" : "file";
    }

    private static String csv(String value) {
        if (value.indexOf(',') < 0 && value.indexOf('"') < 0 && value.indexOf('\n') < 0) {
            return value;
        }
        return '"' + value.replace("\"", "\"\"") + '"';
    }

    private static byte[] readFully(FileChannel channel, long position, int length)
            throws IOException {
        if (length < 0) {
            return null;
        }
        byte[] out = new byte[length];
        ByteBuffer buffer = ByteBuffer.wrap(out);
        long pos = position;
        while (buffer.hasRemaining()) {
            int read = channel.read(buffer, pos);
            if (read < 0) {
                return null;
            }
            pos += read;
        }
        return out;
    }

    private static byte[] decompress(int type, byte[] payload) throws IOException {
        return switch (type) {
            case 1 -> {
                try (InputStream in = new GZIPInputStream(new ByteArrayInputStream(payload))) {
                    yield readAll(in);
                }
            }
            case 2 -> {
                try (InputStream in = new InflaterInputStream(new ByteArrayInputStream(payload))) {
                    yield readAll(in);
                }
            }
            case 3 -> payload;
            default -> throw new IOException("unsupported region compression: " + type);
        };
    }

    private static byte[] readAll(InputStream in) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream(Math.max(256, in.available() * 4));
        byte[] buffer = new byte[16384];
        int read;
        while ((read = in.read(buffer)) >= 0) {
            out.write(buffer, 0, read);
        }
        return out.toByteArray();
    }
}
