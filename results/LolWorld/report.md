# Differential backup benchmark - LolWorld

**Created:** 2026-10-22T19:21:38+0800  
**Snapshots:** 5  
**Repository:** https://github.com/moltony/LolWorld at master  
**Commits:** 8 total, 5 effective, 3 skipped  
**Configuration:** zstd L3 / default  
**Engine:** `$MINIMAL_BACKUP` (sha256 ef7566fdc1e2...)  
**Machine:** 12th Gen Intel(R) Core(TM) i5-12450H, 12 cores, openjdk version "25.0.4" 2026-07-21 LTS

## Headline

| Metric | Value |
| --- | ---: |
| Vault after 5 snapshots | **22.73 MB** |
| Full working trees | 149.92 MB |
| Vault / full trees | **15.16%** |
| Git repository on disk | 86.57 MB |
| Vault / git repository | **26.25%** |
| Vault / last full snapshot | 1.123x |
| Median append per snapshot | 1.97 MB |
| Largest append | 3.39 MB |
| Round-trip failures | 0 |
| Skipped records | 0 |

## Findings

* Vault after 5 restore points: **22.73 MB** (15.16% of 149.92 MB of working trees, 26.25% of the git repository, 1.12x one full snapshot).
* Baseline: 15.01 MB (66.1% of the vault); the other 4 snapshots added 7.71 MB.
* Median append after the baseline: 1.97 MB (9.73% of a full snapshot). Largest: snapshot 5 (00005-20230813-062140-3f9a761) at 3.39 MB.
* Smallest vault: zstd L9 / default at 20.66 MB (90.89% of zstd L3 / default).

## Per-snapshot results

| # | Version | Source | World | Targets | New | Chg | Del | Logical | Full | Append | Append/Full | Vault | Time s |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `00001-20230804-140453-a19c878` | 26.88 MB | 26.88 MB | 4,270 | 0 | 0 | 0 | 94.49 MB | 15.01 MB | 15.01 MB | 100.00% | 15.01 MB | 2.20 |
| 2 | `00002-20230812-144017-a415091` | 27.11 MB | 27.11 MB | 4,280 | 41 | 2,432 | 31 | 94.87 MB | 15.08 MB | 390.65 kB | 2.59% | 15.40 MB | 2.68 |
| 3 | `00003-20230812-151500-921d3b2` | 30.02 MB | 30.02 MB | 4,666 | 469 | 3,048 | 83 | 107.97 MB | 17.04 MB | 2.71 MB | 15.89% | 18.11 MB | 3.32 |
| 4 | `00004-20230812-154255-b59bb1d` | 31.25 MB | 31.25 MB | 4,843 | 191 | 2,782 | 14 | 112.61 MB | 17.75 MB | 1.23 MB | 6.92% | 19.34 MB | 2.78 |
| 5 | `00005-20230813-062140-3f9a761` | 34.67 MB | 34.67 MB | 5,017 | 219 | 2,206 | 45 | 128.65 MB | 20.23 MB | 3.39 MB | 16.73% | 22.73 MB | 3.56 |

## Codec comparison

| Configuration | First full | Last full | Vault | Vault/copies | Median append | Time s | Failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| zstd L3 / default | 15.01 MB | 20.23 MB | 22.73 MB | 15.16% | 1.97 MB | 14.5 | 0 |
| zstd L9 / default | 13.59 MB | 18.25 MB | 20.66 MB | 13.78% | 1.81 MB | 19.8 | 0 |

## Method and caveats

* Content-hash diff, not write capture: incremental numbers are a lower bound for a server that rewrites unchanged data.
* Only the NBT pipeline is stored; JSON/datapack/config bytes are outside the vault.
* Append-only: no GC, keyframes or compaction.
* 42-byte block headers and the block index cache are charged; filesystem rounding is not.
* Timings are indicative single-run wall clock; byte counts are deterministic.
* Git input: 8 commits, 5 effective; the rest only changed files the engine ignores (docs, logs, session.lock, level.dat_old). Each commit was materialised before scanning; prepare time is excluded from the scan columns.
* Source bytes for a commit are an uncompressed working-tree checkout; the git repository size is packed, so the two baselines measure different things.

The self-contained visual report is `report.html` in this directory.

