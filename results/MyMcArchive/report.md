# Differential backup benchmark - MyMcArchive

**Created:** 2026-10-22T17:57:51+0800  
**Snapshots:** 7  
**Repository:** https://github.com/NvFls/MyMcArchive at master  
**Commits:** 9 total, 7 effective, 2 skipped  
**Configuration:** zstd L3 / default  
**Engine:** `$MINIMAL_BACKUP` (sha256 ef7566fdc1e2...)  
**Machine:** 12th Gen Intel(R) Core(TM) i5-12450H, 12 cores, openjdk version "25.0.4" 2026-07-21 LTS

## Headline

| Metric | Value |
| --- | ---: |
| Vault after 7 snapshots | **395.95 MB** |
| Full working trees | 4.54 GB |
| Vault / full trees | **8.73%** |
| Git repository on disk | 970.17 MB |
| Vault / git repository | **40.81%** |
| Vault / last full snapshot | 1.031x |
| Median append per snapshot | 1.39 MB |
| Largest append | 8.86 MB |
| Round-trip failures | 0 |
| Skipped records | 0 |

## Findings

* Vault after 7 restore points: **395.95 MB** (8.73% of 4.54 GB of working trees, 40.81% of the git repository, 1.03x one full snapshot).
* Baseline: 377.11 MB (95.2% of the vault); the other 6 snapshots added 18.84 MB.
* Median append after the baseline: 1.39 MB (0.36% of a full snapshot). Largest: snapshot 7 (00007-20240729-172014-a2a392f) at 8.86 MB.
* Smallest vault: zstd L9 / default at 357.21 MB (90.22% of zstd L3 / default).

## Per-snapshot results

| # | Version | Source | World | Targets | New | Chg | Del | Logical | Full | Append | Append/Full | Vault | Time s |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `00001-20240405-033901-5cae626` | 645.74 MB | 645.74 MB | 96,714 | 0 | 0 | 0 | 2.39 GB | 377.11 MB | 377.11 MB | 100.00% | 377.11 MB | 45.63 |
| 2 | `00002-20240704-174941-7fcd4cb` | 646.03 MB | 646.03 MB | 96,728 | 204 | 8,398 | 190 | 2.39 GB | 377.14 MB | 1.68 MB | 0.44% | 378.78 MB | 15.67 |
| 3 | `00003-20240717-155742-a39a83f` | 646.08 MB | 646.08 MB | 96,652 | 181 | 6,731 | 257 | 2.39 GB | 377.19 MB | 1.11 MB | 0.30% | 379.90 MB | 13.40 |
| 4 | `00004-20240723-160107-d4bc10a` | 646.13 MB | 646.13 MB | 96,717 | 164 | 4,276 | 99 | 2.39 GB | 377.30 MB | 738.21 kB | 0.20% | 380.63 MB | 10.29 |
| 5 | `00005-20240724-083428-a507293` | 646.16 MB | 646.16 MB | 96,731 | 55 | 4,441 | 41 | 2.39 GB | 377.32 MB | 608.39 kB | 0.16% | 381.24 MB | 11.04 |
| 6 | `00006-20240728-141826-9469426` | 648.60 MB | 648.60 MB | 96,923 | 628 | 13,538 | 436 | 2.40 GB | 378.65 MB | 5.85 MB | 1.54% | 387.09 MB | 22.21 |
| 7 | `00007-20240729-172014-a2a392f` | 656.63 MB | 656.63 MB | 97,839 | 1,464 | 11,577 | 548 | 2.44 GB | 383.90 MB | 8.86 MB | 2.31% | 395.95 MB | 20.08 |

## Codec comparison

| Configuration | First full | Last full | Vault | Vault/copies | Median append | Time s | Failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| zstd L3 / default | 377.11 MB | 383.90 MB | 395.95 MB | 8.73% | 1.39 MB | 138.3 | 0 |
| zstd L9 / default | 339.91 MB | 345.96 MB | 357.21 MB | 7.88% | 1.31 MB | 205.7 | 0 |

## Method and caveats

* Content-hash diff, not write capture: incremental numbers are a lower bound for a server that rewrites unchanged data.
* Only the NBT pipeline is stored; JSON/datapack/config bytes are outside the vault.
* Append-only: no GC, keyframes or compaction.
* 42-byte block headers and the block index cache are charged; filesystem rounding is not.
* Timings are indicative single-run wall clock; byte counts are deterministic.
* Git input: 9 commits, 7 effective; the rest only changed files the engine ignores (docs, logs, session.lock, level.dat_old). Each commit was materialised before scanning; prepare time is excluded from the scan columns.
* Source bytes for a commit are an uncompressed working-tree checkout; the git repository size is packed, so the two baselines measure different things.

The self-contained visual report is `report.html` in this directory.

