# miniback-benchmark

A dedicated benchmark for differential world backups. Give it a series of **progressive
full saves** (each one a complete copy of the world, oldest first) and it replays them
through the engine's real checkpoint policy, then writes a self-contained visual report.

The engine under test is compiled read-only from `../minimal-backup` by default and can be
pointed anywhere with `--project`.

## Quick start

```bash
# 1. Drop snapshots into saves/ (one directory or archive per restore point)
./bench.py run --saves saves --levels 3,9 --long off,on --name my-run

# 2. Open the visual report
xdg-open results/my-run/report.html
```

No third-party Python packages are needed. The HTML report is one file with inline SVG
charts and inline CSS: it works offline and can be sent to someone as-is.

## Input layouts

`--saves DIR` treats every immediate child of `DIR` as one snapshot. Supported children:

| Child | Meaning |
| --- | --- |
| directory with `level.dat` or `region/` | the world root itself |
| directory containing `world/` | a server-style save directory |
| `*.tar.gz`, `*.tgz`, `*.tar`, `*.zip` | an archive extracted to `work/extract/` |
| anything else | ignored |

Snapshots are ordered by **natural filename order**, so `2-world` comes before
`10-world`. Prefix names with zero-padded numbers if the names are not chronological.
`--order mtime` sorts by modification time instead.

### Explicit manifest

For full control (custom labels, archives stored elsewhere, a compressed-size baseline):

```tsv
# label<TAB>worldDir<TAB>sourceBytes(optional)
2026-08-20T22:40  /backups/world-01/world  78435405
2026-08-20T22:41  /backups/world-02/world  78463433
```

`sourceBytes` is the size of the original full save (an archive). It is used only for the
"full copies on disk" comparison; when omitted, the directory size is used.

### Git-backed histories

A repository of full saves can be benchmarked commit by commit without checking out every
commit at once. `tools/git_dataset.py` turns a bare clone into an engine manifest, and
`tools/git_materialize.py` updates one live directory before each snapshot is scanned.

```bash
git clone --bare https://github.com/NvFls/MyMcArchive repos/MyMcArchive.git
python3 tools/git_dataset.py \
  --git-dir repos/MyMcArchive.git --url https://github.com/NvFls/MyMcArchive \
  --dest work/git/MyMcArchive \
  --manifest datasets/MyMcArchive/manifest.tsv \
  --meta datasets/MyMcArchive/dataset.json

BENCH_RESULTS=/data/bench/results ./bench.py run \
  --manifest datasets/MyMcArchive/manifest.tsv --raw-manifest \
  --meta datasets/MyMcArchive/dataset.json --name MyMcArchive --levels 3,9
```

A commit is **effective** when it changes at least one file the engine tracks. Commits that
only touch READMEs, logs, `session.lock`, `level.dat_old` or other ignored files are skipped.
Each snapshot's manifest line carries a change list, so DiffBench scans only the region files
that moved and carries the rest of the target state forward; byte counts are identical to a
full scan, while a 2500-commit history becomes practical.

`datasets/public-git-repos.tsv` lists the eight public repositories used for the reference
study (all completed). Results live outside the source tree when `BENCH_RESULTS` points at a
larger disk:

```bash
BENCH_RESULTS=/run/media/link/F0D66DC87F238D7E/test-miniback/results ./bench.py list
```

### Legacy zip bundle

A zip whose members are full-save `.tar.gz` files (one per restore point) is supported:

```bash
./bench.py run --zip /path/to/mc-backups.zip --name legacy
```

The member name becomes the label and the member's compressed size becomes its source size.

## Commands

| Command | What it does |
| --- | --- |
| `./bench.py run ...` | resolve/extract snapshots, compile the engine, run the matrix, write the report |
| `./bench.py report results/<study>` | rebuild `report.html` / `report.md` from existing CSVs |
| `./bench.py list` | list studies under `results/` |

Run options:

| Option | Default | Meaning |
| --- | --- | --- |
| `--saves` / `--zip` / `--manifest` | - | input (exactly one) |
| `--levels` | `3` | comma-separated zstd levels, e.g. `3,9` |
| `--long` | `off` | comma-separated long-distance flags, e.g. `off,on` |
| `--project` | `../minimal-backup` | engine source tree compiled into `out/engine` |
| `--heap` | `12g` | JVM heap per run |
| `--name` | timestamp | study directory name under `results/` |
| `--zstd` | auto | path to `zstd-jni-*.jar` (otherwise searched in the Gradle cache) |
| `--force` | off | replace an existing study with the same name |

## Publish to GitHub Pages

`results/` is a self-contained site. Build a publishable copy (large change logs gzipped, local
paths replaced with `$PROJECT` / `$BENCH_BASE`, reports regenerated against the published
files):

```bash
./tools/build_site.py --results /path/to/results --out results
```

The script writes `results/index.html`, `results/overview.html`, `.nojekyll` and one
`report.html` per study. `.github/workflows/pages.yml` uploads `results/` and deploys it with
the official Pages actions. In the repository settings choose **Pages -> Build and deployment ->
GitHub Actions**.

The published tree is Git-friendly: change logs above 20 MB are gzipped, and the reports link
to `changes.csv.gz` automatically. GitHub Pages has a 1 GB site limit.

## Output layout

```
results/<study>/
  study.json          dataset, engine hash, environment, run matrix, exact argv
  manifest.tsv        resolved label -> world -> source bytes, in benchmark order
  zstd-l3/            one directory per configuration
    versions.csv      per-snapshot totals
    families.csv      chunk vs file split
    regions.csv       per-file activity (feeds the heatmap)
    changes.csv       every new/changed/deleted target
    skipped.csv       records rejected by Anvil/NBT validation
    log.txt           engine stdout
    command.txt       exact java command
  zstd-l9/
  zstd-l3-long/
  zstd-l9-long/
  report.html         self-contained visual report
  report.md           the same results as Markdown tables
```

## What is measured

For every snapshot the runner reconstructs the targets the engine tracks:

* every non-empty chunk in every `region/`, `entities/` and `poi/` `.mca` file, including
  custom dimensions;
* every `level.dat`, `playerdata/*.dat` and `data/**/*.dat` whole-file target.

The first snapshot is written as a FULL baseline. Each later snapshot is diffed against the
immediately previous one by **canonical NBT bytes**, and the checkpoint policy is replayed:

| Situation | What is appended |
| --- | --- |
| changed target | DELTA + 42-byte header |
| new target | FULL + ABSENT marker + two headers |
| deleted target | ABSENT marker + header |
| unchanged target | nothing |

Every FULL and DELTA block is decompressed and byte-compared after writing
(`roundtrip_fail`); the report shows the total.

### Columns

| Column | Meaning |
| --- | --- |
| `source_bytes` | size of the original full save (archive or directory) |
| `world_bytes` | size of the extracted world on disk |
| `logical_bytes` | sum of canonical NBT lengths for all targets |
| `full_total` | hypothetical full snapshot: all targets FULL + headers |
| `actual_full_total` | `full_total` + block index cache + file headers |
| `incr_total` | bytes appended for this snapshot (payload + headers) |
| `cache_bytes` | block index cache appended (`.zpack` entries + file headers) |
| `actual_incr_total` | `incr_total` + `cache_bytes` — **the number the vault grows by** |
| `actual_cumulative_min` | vault size after this snapshot |
| `cumulative_source` | cost of keeping one full copy per snapshot up to here |

"Append/Full" is `actual_incr_total / actual_full_total`: what this restore point costs
relative to taking an independent full backup.

## Report contents

The HTML report has KPI cards, then:

1. **Storage over time** — vault vs one-full-copy-per-snapshot vs a single full snapshot.
2. **What each snapshot costs** — log-scale appends with append/full % overlay.
3. **Where the append goes** — stacked new FULL / DELTA / headers / cache.
4. **Target churn** — new, changed and deleted targets per snapshot.
5. **File activity over time** — heatmap of the 18 busiest region/entity/poi/dat files.
6. **Target families** — chunk vs whole-file appends.
7. **Codec comparison** — vault, median append and timings for every configuration.
8. **Per-snapshot detail, family totals, largest deltas** — the full table.
9. **Method and caveats** — accounting and the exact command that produced the study.

## Bundled dataset

`work/` already contains the 19 extracted saves used during development (5.1 GB) and the
original archives. To rerun the reference study:

```bash
./run-bench.sh                 # 19 snapshots, zstd 3/9 x long off/on
# or explicitly:
./bench.py run --manifest datasets/legacy-19.tsv --name legacy-19 \
  --levels 3,9 --long off,on
```

`work/` is only an extraction cache and can be deleted; `results/` keeps the CSV evidence
and the reports.

## Requirements

* Python 3.12+ (stdlib only; uses `tarfile.extractall(filter=...)`)
* JDK 17+ (`javac` and `java` on `PATH`)
* `zstd-jni` jar, normally found in the Gradle cache; otherwise pass `--zstd`

## Caveats

* **Content-hash diff, not write capture.** A target counts as changed only when its
  canonical bytes differ from the previous snapshot. A live server that rewrites unchanged
  data would append small deltas that this benchmark does not charge, so incremental numbers
  are a lower bound.
* **Scope.** Only the NBT pipeline is stored. Datapacks, JSON, SNBT and configs are counted
  in "World" but not in the vault.
* **Append-only.** No GC, keyframes or compaction; a real GC could reduce the vault.
* **Accounting.** 42-byte block headers and the block index cache are charged; filesystem
  block rounding and `index.properties` are not.
* **Timings.** Single warm-cache run on one machine. Byte counts are deterministic; times
  are indicative.
