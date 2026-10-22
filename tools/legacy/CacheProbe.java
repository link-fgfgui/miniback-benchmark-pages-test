import io.github.linkfgfgui.minimalbackup.engine.Block;
import io.github.linkfgfgui.minimalbackup.engine.BlockFile;
import io.github.linkfgfgui.minimalbackup.engine.BlockTable;
import io.github.linkfgfgui.minimalbackup.engine.Xxh64;
import io.github.linkfgfgui.minimalbackup.engine.ZstdDelta;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;

public final class CacheProbe {
    public static void main(String[] args) throws Exception {
        Path file = Path.of("/tmp/miniback-cache-probe.zpack");
        Files.deleteIfExists(file);
        BlockTable table = BlockTable.empty();
        List<BlockFile.NewBlock> blocks = new ArrayList<>();
        int count = 300;
        Random random = new Random(42);
        for (int i = 0; i < count; i++) {
            byte[] raw = new byte[96];
            random.nextBytes(raw);
            byte[] payload = ZstdDelta.compressFull(raw, 3);
            Block block = Block.create(i + 1, 0, 1, i, Block.TYPE_FILE,
                    Block.MODE_FULL, raw.length, Xxh64.hash(raw), payload.length);
            blocks.add(new BlockFile.NewBlock(block, payload));
        }
        long cache = BlockFile.append(file, table, blocks, -1L, true);
        long length = BlockFile.cacheLength(file, cache);
        System.out.println("cacheLength=" + length + " entries=" + count
                + " bytesPerEntry=" + String.format("%.2f", (length - 20.0) / count)
                + " v1WouldBe=" + (20 + 30 * count));
        System.out.println("table=" + BlockFile.loadTable(file, cache).blocks().size());
    }
}
