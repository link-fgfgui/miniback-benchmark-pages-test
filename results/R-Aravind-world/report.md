# Differential backup benchmark - R-Aravind-world

**Created:** 2026-10-22T18:12:44+0800  
**Snapshots:** 9  
**Repository:** https://github.com/R-Aravind/world at master  
**Commits:** 10 total, 9 effective, 1 skipped  
**Configuration:** zstd L3 / default  
**Engine:** `$MINIMAL_BACKUP` (sha256 ef7566fdc1e2...)  
**Machine:** 12th Gen Intel(R) Core(TM) i5-12450H, 12 cores, openjdk version "25.0.4" 2026-07-21 LTS

## Headline

| Metric | Value |
| --- | ---: |
| Vault after 9 snapshots | **704.52 MB** |
| Full working trees | 5.86 GB |
| Vault / full trees | **12.02%** |
| Git repository on disk | 1.53 GB |
| Vault / git repository | **46.13%** |
| Vault / last full snapshot | 1.094x |
| Median append per snapshot | 76.40 MB |
| Largest append | 180.08 MB |
| Round-trip failures | 0 |
| Skipped records | 0 |

## Findings

* Vault after 9 restore points: **704.52 MB** (12.02% of 5.86 GB of working trees, 46.13% of the git repository, 1.09x one full snapshot).
* Baseline: 64.57 MB (9.2% of the vault); the other 8 snapshots added 639.95 MB.
* Median append after the baseline: 76.40 MB (11.86% of a full snapshot). Largest: snapshot 2 (00002-20220129-113003-4f2144f) at 180.08 MB.

## Per-snapshot results

| # | Version | Source | World | Targets | New | Chg | Del | Logical | Full | Append | Append/Full | Vault | Time s |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `00001-20220128-111624-07ad997` | 103.50 MB | 103.50 MB | 14,837 | 0 | 0 | 0 | 389.42 MB | 64.57 MB | 64.57 MB | 100.00% | 64.57 MB | 8.35 |
| 2 | `00002-20220129-113003-4f2144f` | 366.55 MB | 366.55 MB | 49,280 | 34,863 | 10,211 | 420 | 1.36 GB | 238.71 MB | 180.08 MB | 75.44% | 244.66 MB | 37.31 |
| 3 | `00003-20220131-170615-952ce44` | 454.94 MB | 454.94 MB | 59,267 | 10,292 | 16,169 | 305 | 1.71 GB | 300.32 MB | 69.99 MB | 23.31% | 314.65 MB | 28.91 |
| 4 | `00004-20220207-083450-6f6dcf9` | 661.10 MB | 661.10 MB | 87,794 | 28,877 | 21,892 | 350 | 2.47 GB | 431.86 MB | 144.50 MB | 33.46% | 459.15 MB | 46.27 |
| 5 | `00005-20220209-141644-8064c9d` | 678.78 MB | 678.78 MB | 90,036 | 2,624 | 6,828 | 382 | 2.55 GB | 444.02 MB | 14.00 MB | 3.15% | 473.14 MB | 13.24 |
| 6 | `00006-20220215-153620-c574d78` | 815.12 MB | 815.12 MB | 107,945 | 18,532 | 24,953 | 623 | 3.06 GB | 530.20 MB | 98.21 MB | 18.52% | 571.36 MB | 44.43 |
| 7 | `00007-20220216-073450-e04774f` | 868.90 MB | 868.90 MB | 115,661 | 7,990 | 6,905 | 274 | 3.25 GB | 563.09 MB | 34.86 MB | 6.19% | 606.22 MB | 15.55 |
| 8 | `00008-20220218-160131-2953ffd` | 892.75 MB | 892.75 MB | 119,755 | 4,444 | 12,792 | 350 | 3.33 GB | 575.27 MB | 15.50 MB | 2.69% | 621.72 MB | 21.89 |
| 9 | `00009-20231110-095418-94cffb9` | 1.02 GB | 1.02 GB | 140,253 | 21,194 | 29,792 | 696 | 3.76 GB | 643.94 MB | 82.80 MB | 12.86% | 704.52 MB | 54.41 |

## Method and caveats

* Content-hash diff, not write capture: incremental numbers are a lower bound for a server that rewrites unchanged data.
* Only the NBT pipeline is stored; JSON/datapack/config bytes are outside the vault.
* Append-only: no GC, keyframes or compaction.
* 42-byte block headers and the block index cache are charged; filesystem rounding is not.
* Timings are indicative single-run wall clock; byte counts are deterministic.
* Git input: 10 commits, 9 effective; the rest only changed files the engine ignores (docs, logs, session.lock, level.dat_old). Each commit was materialised before scanning; prepare time is excluded from the scan columns.
* Source bytes for a commit are an uncompressed working-tree checkout; the git repository size is packed, so the two baselines measure different things.

The self-contained visual report is `report.html` in this directory.

