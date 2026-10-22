#!/usr/bin/env python3
"""Build results/REPORT.md from the DiffBench CSV outputs."""
import csv
import os
import statistics

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(run):
    root = os.path.join(BASE, "results", run)
    versions = list(csv.DictReader(open(os.path.join(root, "versions.csv"))))
    families = list(csv.DictReader(open(os.path.join(root, "families.csv"))))
    changes = list(csv.DictReader(open(os.path.join(root, "changes.csv"))))
    return versions, families, changes


def mb(value):
    return f"{int(value) / 1e6:.2f}"


def pct(value):
    return f"{float(value):.2f}%"


v3, f3, c3 = load("run2")
v9, f9, c9 = load("run-level3-long")
vl9, fl9, cl9 = load("run-level9")

archive_total = sum(int(r["archive_bytes"]) for r in v3)
vault3 = int(v3[-1]["actual_cumulative_min"])
vault_long = int(v9[-1]["actual_cumulative_min"])
vault9 = int(vl9[-1]["actual_cumulative_min"])
first3 = int(v3[0]["actual_full_total"])
last3 = int(v3[-1]["actual_full_total"])
first9 = int(vl9[0]["actual_full_total"])
last9 = int(vl9[-1]["actual_full_total"])
sum_incr3 = sum(int(r["actual_incr_total"]) for r in v3[1:])
sum_incr9 = sum(int(r["actual_incr_total"]) for r in vl9[1:])
sum_delta3 = sum(int(r["delta_payload"]) for r in v3)
sum_delta9 = sum(int(r["delta_payload"]) for r in vl9)
sum_new3 = sum(int(r["new_full_payload"]) for r in v3)
sum_new9 = sum(int(r["new_full_payload"]) for r in vl9)
changed3 = sum(int(r["changed"]) for r in v3)
new3 = sum(int(r["new"]) for r in v3)
deleted3 = sum(int(r["deleted"]) for r in v3)
changed_target_full3 = sum(int(x["full_bytes"]) for x in c3)
changed_target_delta3 = sum(int(x["delta_bytes"]) for x in c3)
changed_target_full9 = sum(int(x["full_bytes"]) for x in cl9)
changed_target_delta9 = sum(int(x["delta_bytes"]) for x in cl9)
hourly3 = [int(r["actual_incr_total"]) for r in v3 if r["version"].startswith("mc-backup")][1:]
hourly9 = [int(r["actual_incr_total"]) for r in vl9 if r["version"].startswith("mc-backup")][1:]
hourly_long = [int(r["actual_incr_total"]) for r in v9 if r["version"].startswith("mc-backup")][1:]

lines = []
lines.append("# Per-version diff benchmark on a real 1.20.1 Forge world")
lines.append("")
lines.append("**Date:** 2026-10-21  ")
lines.append("**Input archive:** `../rewind-others/mc-backups.zip` (19 full-world `tar.gz` backups)  ")
lines.append("**Project under test:** `../minimal-backup` (read-only; engine compiled into this benchmark's `out/`)  ")
lines.append("**Workspace:** `miniback-benchmark/`  ")
lines.append("**Codec:** `zstd/1`, level 3 (default), long-distance matching off unless noted  ")
lines.append("")
lines.append("## What was measured")
lines.append("")
lines.append("Every archive was extracted and replayed through the project's own engine code "
             "(`NbtCanon`, `TreeAligner`, `Codec`/`ZstdDelta`, "
             "`AnvilRegion`, `Xxh64`). For each version the benchmark reconstructs "
             "the same targets the mod tracks:")
lines.append("")
lines.append("* every non-empty chunk in every `region/`, `entities/` and "
             "`poi/` `.mca` file, including custom dimensions;")
lines.append("* every `level.dat`, `playerdata/*.dat` and "
             "`data/**/*.dat` whole-file target.")
lines.append("")
lines.append("The first version is written as a FULL baseline. Each later version is diffed "
             "against the immediately previous one with the checkpoint's real policy: DELTA for "
             "a changed target, FULL + 42-byte ABSENT marker for a new target, ABSENT for a "
             "deleted target, nothing for an unchanged target. Canonicalisation and palette "
             "alignment are the project's own. Every block is decompressed and byte-compared "
             "after compression; `roundtrip_fail=0` in every row. The 42-byte block header, "
             "the 30-byte-per-block `.zpack` cache entry and the 28-byte file/cache header are "
             "modeled from `BlockFile`'s layout and counted; filesystem block rounding and "
             "`index.properties` are not.")
lines.append("")
lines.append("The comparison baseline is the rewind archive itself: each `tar.gz` is a "
             "complete world copy, so 19 restore points cost the sum of the 19 archives. The mod "
             "stores only the NBT pipeline by default (`copyJson=false`), so the 1.5-1.8 MB "
             "of JSON/SNBT/datapack/config files per version is outside its scope and is not "
             "counted in the vault; the rewind archives do contain it.")
lines.append("")
lines.append("## Dataset")
lines.append("")
lines.append("| Item | Value |")
lines.append("| --- | --- |")
lines.append("| Restore points | 19 (6 manual Aug 20/22, 1 manual Oct 7, 12 hourly Oct 10-11) |")
lines.append("| Minecraft / loader | 1.20.1 Forge, modded (custom dimensions, FTB, Create/AE2/Mekanism-era data) |")
lines.append(f"| World size on disk | {mb(v3[0]['world_bytes'])} MB -> {mb(v3[-1]['world_bytes'])} MB |")
lines.append("| Region/entity/POI files | 252 -> 375 |")
lines.append(f"| Targets | {int(v3[0]['targets']):,} -> {int(v3[-1]['targets']):,} "
             f"({int(v3[0]['chunks']):,} -> {int(v3[-1]['chunks']):,} chunks, "
             f"{int(v3[0]['files'])} -> {int(v3[-1]['files'])} files) |")
lines.append(f"| Logical (canonical NBT) bytes | {mb(v3[0]['logical_bytes'])} MB -> "
             f"{mb(v3[-1]['logical_bytes'])} MB |")
lines.append(f"| Rewind archives total | {mb(archive_total)} MB ({archive_total:,} B) |")
lines.append(f"| Untracked non-NBT bytes / version | {mb(v3[0]['untracked_bytes'])} - "
             f"{mb(v3[-1]['untracked_bytes'])} MB |")
lines.append("")
lines.append("All valid chunk records were zlib-compressed NBT; no external `.mcc` chunks "
             "and no LZ4/custom compression appeared. A handful of stale region-header entries "
             "per snapshot (6, 5 and 5 in the first three, 4 afterwards) were dropped by the "
             "engine's own "
             "`AnvilRegion` validation; no valid target was skipped "
             "(`skipped.csv` is header-only).")
lines.append("")
lines.append("## Per-version results (default `zstd/1` level 3)")
lines.append("")
lines.append("`Full` is the hypothetical cost of an independent full snapshot of that "
             "version (all targets FULL). `Increment` is what the append-only vault "
             "actually writes for that version. `Vault` and `Rewind` are cumulative.")
lines.append("")
lines.append("| # | Version | Archive MB | World MB | Targets | New | Chg | Del | Logical MB | Full MB | Increment MB | Incr/Full | Vault MB | Rewind MB | Time s |")
lines.append("| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
for i, r in enumerate(v3, 1):
    lines.append(
        f"| {i} | `{r['version']}` | {mb(r['archive_bytes'])} | {mb(r['world_bytes'])} | "
        f"{int(r['targets']):,} | {r['new']} | {r['changed']} | {r['deleted']} | "
        f"{mb(r['logical_bytes'])} | {mb(r['actual_full_total'])} | "
        f"{mb(r['actual_incr_total'])} | "
        f"{100 * int(r['actual_incr_total']) / int(r['actual_full_total']):.2f}% | "
        f"{mb(r['actual_cumulative_min'])} | "
        f"{mb(r['cumulative_rewind'])} | {int(r['total_ms']) / 1000:.2f} |")
lines.append("")
lines.append("## Aggregate")
lines.append("")
lines.append("| Metric | Level 3 (default) | Level 9 |")
lines.append("| --- | ---: | ---: |")
lines.append(f"| First full snapshot | {mb(first3)} MB | {mb(first9)} MB |")
lines.append(f"| Full snapshot of the last version | {mb(last3)} MB | {mb(last9)} MB |")
lines.append(f"| Vault after 19 restore points | **{mb(vault3)} MB** | **{mb(vault9)} MB** |")
lines.append(f"| Vault / 19 rewind archives ({mb(archive_total)} MB) | **{100 * vault3 / archive_total:.2f}%** | "
             f"**{100 * vault9 / archive_total:.2f}%** |")
lines.append(f"| Vault / one full snapshot of the last version | {vault3 / last3:.3f}x | "
             f"{vault9 / last9:.3f}x |")
lines.append(f"| Sum of the 18 increments after the baseline | {mb(sum_incr3)} MB | {mb(sum_incr9)} MB |")
lines.append(f"| Median steady-state hourly increment | {mb(statistics.median(hourly3))} MB | "
             f"{mb(statistics.median(hourly9))} MB |")
lines.append(f"| Largest increment (2026-10-07 world expansion) | "
             f"{mb(max(int(r['actual_incr_total']) for r in v3[1:]))} MB | "
             f"{mb(max(int(r['actual_incr_total']) for r in vl9[1:]))} MB |")
lines.append(f"| Changed targets over 18 diff steps | {changed3:,} | {changed3:,} |")
lines.append(f"| New targets over 18 diff steps | {new3:,} | {new3:,} |")
lines.append(f"| Deleted targets over 18 diff steps | {deleted3:,} | {deleted3:,} |")
lines.append(f"| Sum of DELTA payload | {mb(sum_delta3)} MB | {mb(sum_delta9)} MB |")
lines.append(f"| Sum of NEW-target FULL payload | {mb(sum_new3)} MB | {mb(sum_new9)} MB |")
lines.append(f"| Changed-target DELTA / FULL | {100 * changed_target_delta3 / changed_target_full3:.1f}% | "
             f"{100 * changed_target_delta9 / changed_target_full9:.1f}% |")
lines.append(f"| Round-trip failures | {sum(int(r['roundtrip_fail']) for r in v3)} | "
             f"{sum(int(r['roundtrip_fail']) for r in vl9)} |")
lines.append("")

blocks_total = int(v3[0]["targets"]) + sum(
    int(r["changed"]) + 2 * int(r["new"]) + int(r["deleted"]) for r in v3[1:])
saved = 28 * blocks_total
vault3_p1b = vault3 - saved
vault9_p1b = vault9 - saved


def median_hour(rows):
    hourly = [r for r in rows if r["version"].startswith("mc-backup")][1:]
    return sorted(hourly, key=lambda r: int(r["actual_incr_total"]))[len(hourly) // 2]


med3 = median_hour(v3)
med9 = median_hour(vl9)
med3_blocks = int(med3["changed"]) + 2 * int(med3["new"]) + int(med3["deleted"])
med9_blocks = int(med9["changed"]) + 2 * int(med9["new"]) + int(med9["deleted"])
hourly3_p1b = int(med3["actual_incr_total"]) - 28 * med3_blocks
hourly9_p1b = int(med9["actual_incr_total"]) - 28 * med9_blocks

lines.append("## Post-implementation note (2026-10-22)")
lines.append("")
lines.append("After this run, P0 and P1b were implemented in the project:")
lines.append("")
lines.append("* **P0** skips a non-ABSENT entry whose aligned bytes equal the previous "
             "**visible** block, and a repeated ABSENT whose previous tombstone is visible. "
             "Abandoned-branch blocks are not used as a no-op base. Checkpoint logs the skip "
             "count at debug level.")
lines.append("* **P1b** writes a v2 cache that stores only block-header offsets as varint "
             "deltas. A 300-block probe measured **2.00 B/entry** (v1: 30 B); v1 caches remain "
             "readable and old readers fall back to scanning.")
lines.append("")
lines.append("Applying 2 B/block to this dataset (the first full may be 2-3 B/block, so treat "
             "this as an estimate):")
lines.append("")
lines.append("| Metric | Pre-change | P1b estimate |")
lines.append("| --- | ---: | ---: |")
lines.append(f"| Vault after 19 restore points (level 3) | {mb(vault3)} MB | {mb(vault3_p1b)} MB |")
lines.append(f"| Vault after 19 restore points (level 9) | {mb(vault9)} MB | {mb(vault9_p1b)} MB |")
lines.append(f"| Median steady-state hour (level 3) | {mb(statistics.median(hourly3))} MB | "
             f"{hourly3_p1b / 1e6:.4f} MB |")
lines.append(f"| Median steady-state hour (level 9) | {mb(statistics.median(hourly9))} MB | "
             f"{hourly9_p1b / 1e6:.4f} MB |")
lines.append("")
lines.append("P0 has no effect on this archive-based diff because no version contained a "
             "rewritten-but-unchanged target (canon_unchanged=0); its benefit is on live servers "
             "that force-save unchanged targets. The tables above remain the pre-change baseline.")
lines.append("")
lines.append("## Codec sensitivity")
lines.append("")
lines.append("| Configuration | First full | Last full | Vault after 19 | Vault / rewind | Median hourly increment | Changed-target DELTA / FULL |")
lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
lines.append(f"| level 3, long off (default) | {mb(first3)} MB | {mb(last3)} MB | {mb(vault3)} MB | "
             f"{100 * vault3 / archive_total:.2f}% | {mb(statistics.median(hourly3))} MB | "
             f"{100 * changed_target_delta3 / changed_target_full3:.1f}% |")
lines.append(f"| level 3, long on | {mb(first3)} MB | {mb(last3)} MB | {mb(vault_long)} MB | "
             f"{100 * vault_long / archive_total:.2f}% | {mb(statistics.median(hourly_long))} MB | "
             f"{100 * sum(int(x['delta_bytes']) for x in c3) / sum(int(x['full_bytes']) for x in c3):.1f}% |")
lines.append(f"| level 9, long off | {mb(first9)} MB | {mb(last9)} MB | {mb(vault9)} MB | "
             f"{100 * vault9 / archive_total:.2f}% | {mb(statistics.median(hourly9))} MB | "
             f"{100 * changed_target_delta9 / changed_target_full9:.1f}% |")
lines.append("")
lines.append(f"Level 9 cuts the full snapshot by {100 * (1 - first9 / first3):.1f}% and the "
             f"19-snapshot vault by {100 * (1 - vault9 / vault3):.1f}%. The "
             "larger effect is on whole-file deltas: at level 3 a 3 MB `level.dat` (Forge "
             "`fml` subtree) produces a ~288 KB delta, almost the 309 KB FULL block, because "
             "the default level-3 window does not reach most of the dictionary. A direct probe "
             "of the 3,087,495-byte `level.dat` pair gives 288,239 B at level 3 and 378 B at "
             "level 9. `long` mode at level 3 shifts the cost between chunks and files but barely "
             "changes the total.")
lines.append("")
lines.append("## Family breakdown (last version, level 3 default)")
lines.append("")
lines.append("| Family | Targets | Full payload | DELTA payload | DELTA / FULL | Total DELTA (19) | Total NEW FULL |")
lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
for fam in ("chunk", "file"):
    fr = [x for x in f3 if x["family"] == fam]
    last = fr[-1]
    lines.append(f"| {fam} | {int(last['targets']):,} | {mb(last['full_payload'])} MB | "
                 f"{mb(last['delta_payload'])} MB | "
                 f"{100 * int(last['delta_payload']) / int(last['full_payload']):.2f}% | "
                 f"{mb(sum(int(x['delta_payload']) for x in fr))} MB | "
                 f"{mb(sum(int(x['new_full_payload']) for x in fr))} MB |")
lines.append("")
lines.append("At level 3 the hourly increment is dominated by whole files, not chunks: in the "
             "last snapshot 151 changed chunks produce 30,490 B of DELTA (about 202 B per chunk), "
             "while 46 changed files produce 291,039 B, almost all of it `level.dat`. At "
             "level 9 the same files produce 3,331 B and the chunks 24,958 B. The chunk side is "
             "already near the noise floor; the file side is the tuning lever.")
lines.append("")
lines.append("## Observations")
lines.append("")
lines.append(f"1. **The baseline dominates.** The first full snapshot is {mb(first3)} MB, "
             f"{100 * first3 / vault3:.0f}% of the {mb(vault3)} MB vault. The 18 later versions add "
             f"only {mb(sum_incr3)} MB in total.")
lines.append(f"2. **Steady state is tiny.** From 14:00 to 00:00 the world changes by a median of "
             f"{mb(statistics.median(hourly3))} MB per hour (level 3), "
             f"{100 * statistics.median(hourly3) / last3:.2f}% of a full snapshot. 40,493 of "
             f"40,690 targets are byte-identical; only ~197 targets change per hour.")
lines.append(f"3. **The Oct 7 jump is growth, not steady state.** 14,688 new targets and 4,384 "
             f"changed targets add {mb(max(int(r['actual_incr_total']) for r in v3[1:]))} MB, still "
             f"less than a third of a fresh full snapshot.")
lines.append(f"4. **19 restore points cost about one full snapshot.** The vault is "
             f"{vault3 / last3:.3f}x the last full snapshot at level 3 and {vault9 / last9:.3f}x at "
             f"level 9, versus 19 full copies in the rewind archive (1.94 GB, "
             f"{archive_total / vault3:.1f}x the vault).")
lines.append(f"5. **Default level 3 is weak on multi-MB whole files.** The hourly "
             f"{mb(statistics.median(hourly3))} MB increment is ~86% `level.dat` delta. Level 9 "
             f"makes the same snapshot {mb(statistics.median(hourly9))} MB and the whole vault "
             f"{mb(vault9)} MB. The project's BENCH.md already recommends level 9; this real-world "
             f"run confirms it with a {100 * (1 - vault9 / vault3):.1f}% vault reduction and a "
             f"{statistics.median(hourly3) / statistics.median(hourly9):.1f}x smaller hourly delta.")
lines.append("6. **No correctness failures.** Every FULL and DELTA block round-tripped "
             "byte-for-byte; no valid target was skipped. The 4-6 stale region-header entries per "
             "snapshot are rejected by the engine's own parser and are not real chunks.")
lines.append("")
lines.append("## Caveats")
lines.append("")
lines.append("* **Content-hash diff, not write capture.** The archives do not record which chunks "
             "the server actually wrote. A target is treated as changed when its canonical bytes "
             "differ from the previous version. A server that rewrites an unchanged chunk would "
             "append a small delta in the real mod; this benchmark does not charge for that, so "
             "the incremental numbers are a lower bound. The FULL baseline is unaffected.")
lines.append("* **Baseline scope is slightly wider than `FullBaselineImporter`.** The "
             "importer reads `region/`, `level.dat`, top-level "
             "`data/*.dat` and `playerdata/*.dat`; entities/POI and nested "
             "`data/` files are captured on their normal read/write hooks. This benchmark "
             "includes all of them from the first version, which makes the baseline slightly "
             "larger (conservative for the savings claim).")
lines.append("* **Scope differs from rewind.** Rewind stores the whole world, including "
             "datapacks, JSON, SNBT and mod configs; minimal-backup's default scope is the NBT "
             "pipeline. The 1.5-1.8 MB/version of untracked files is not in the vault. With "
             "`copyJson=true` the JSON files would be added as full copies (no delta), so "
             "the vault would grow by roughly that amount per snapshot.")
lines.append("* **Append-only, no GC/keyframes.** `keyframeInterval=-1`, no compaction. A "
             "real `/backup gc` would rewrite chains and could reduce the vault. The "
             "42-byte header and the 30-byte-per-block `.zpack` cache entry are counted; "
             "filesystem block rounding and `index.properties` are not.")
lines.append("* **Single machine, warm cache, single run.** Timings are wall clock on this "
             "workstation (12 threads, NVMe, JDK 25). The first version includes JIT warm-up; "
             "later versions are 1.2-2.5 s. Byte counts are deterministic.")
lines.append("* **Uneven spacing.** The 19 archives are not hourly throughout: six manual "
             "backups in Aug, one on Oct 7, then 12 hourly. The 13:00 hourly increment (0.74 MB) "
             "still includes the post-gap reconciliation; the 14:00-00:00 median is the steady "
             "state.")
lines.append("")
lines.append("## Reproduce")
lines.append("")
lines.append("```bash")
lines.append("cd /home/link/Documents/mcmoddev/miniback-benchmark")
lines.append("unzip -o -q /home/link/Documents/mcmoddev/rewind-others/mc-backups.zip 'mc-backups/*.tar.gz' -d work/archives")
lines.append("while IFS= read -r f; do")
lines.append("  label=$(basename \"$f\" .tar.gz)")
lines.append("  mkdir -p \"work/worlds/$label\" && tar -xzf \"$f\" -C \"work/worlds/$label\"")
lines.append("done < <(find work/archives/mc-backups -name '*.tar.gz' | sort)")
lines.append("ZSTD=$(find ~/.gradle/caches/modules-2/files-2.1/com.github.luben/zstd-jni \\")
lines.append("  -name 'zstd-jni-*.jar' ! -name '*-sources.jar' | sort | tail -1)")
lines.append("javac --release 17 -cp \"$ZSTD\" -d out/engine \\")
lines.append("  $(find ../minimal-backup/src/main/java/io/github/linkfgfgui/minimalbackup/engine -name '*.java')")
lines.append("javac --release 17 -cp \"$ZSTD:out/engine\" -d out/tools tools/DiffBench.java")
lines.append("java -Xmx12g -cp \"$ZSTD:out/engine:out/tools\" DiffBench work/worlds work/archives results/run2 3")
lines.append("java -Dbench.long=true -Xmx12g -cp \"$ZSTD:out/engine:out/tools\" DiffBench work/worlds work/archives results/run-level3-long 3")
lines.append("java -Xmx12g -cp \"$ZSTD:out/engine:out/tools\" DiffBench work/worlds work/archives results/run-level9 9")
lines.append("python3 tools/make_report.py")
lines.append("```")
lines.append("")
lines.append("Raw outputs: `results/run2/` (default), `results/run-level3-long/`, "
             "`results/run-level9/`; each contains `versions.csv`, "
             "`families.csv`, `changes.csv` and `skipped.csv`. `work/` is a 5.1 GB "
             "extraction cache; it can be deleted once the CSVs exist.")
lines.append("")

out = os.path.join(BASE, "results", "REPORT.md")
open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("wrote", out)
