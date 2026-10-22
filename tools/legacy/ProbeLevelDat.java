import io.github.linkfgfgui.minimalbackup.engine.Block;
import io.github.linkfgfgui.minimalbackup.engine.Codec;
import io.github.linkfgfgui.minimalbackup.engine.EngineSettings;
import io.github.linkfgfgui.minimalbackup.engine.nbt.NbtCanon;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.zip.GZIPInputStream;

public final class ProbeLevelDat {
    public static void main(String[] args) throws Exception {
        byte[] oldRaw = gunzip(Files.readAllBytes(Path.of(args[0])));
        byte[] newRaw = gunzip(Files.readAllBytes(Path.of(args[1])));
        NbtCanon.Result oldC = NbtCanon.canonicalize(oldRaw);
        NbtCanon.Result newC = NbtCanon.canonicalize(newRaw);
        byte[] aligned = NbtCanon.alignCanonical(oldC.bytes(), newC);
        System.out.println("raw old/new=" + oldRaw.length + "/" + newRaw.length
                + " canonical old/new=" + oldC.bytes().length + "/" + newC.bytes().length
                + " aligned=" + aligned.length);
        for (int level : new int[]{3, 9}) {
            EngineSettings settings = new EngineSettings(level, false,
                    EngineSettings.MAX_ZSTD_LONG_WINDOW_LOG, -1, true);
            byte[] full = Codec.compressFull(newC.bytes(), level, Block.TYPE_FILE);
            byte[] delta = Codec.compressDelta(aligned, oldC.bytes(), settings, Block.TYPE_FILE);
            System.out.println("level=" + level + " full=" + full.length + " delta=" + delta.length);
        }
    }

    private static byte[] gunzip(byte[] file) throws Exception {
        try (InputStream in = new GZIPInputStream(new ByteArrayInputStream(file))) {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[16384];
            int n;
            while ((n = in.read(buf)) >= 0) {
                out.write(buf, 0, n);
            }
            return out.toByteArray();
        }
    }
}
