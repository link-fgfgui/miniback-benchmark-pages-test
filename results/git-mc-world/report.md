# Differential backup benchmark - git-mc-world

**Created:** 2026-10-22T19:20:58+0800  
**Snapshots:** 8  
**Repository:** https://github.com/wavejumper3/git-mc-world at main  
**Commits:** 9 total, 8 effective, 1 skipped  
**Configuration:** zstd L3 / default  
**Engine:** `$MINIMAL_BACKUP` (sha256 ef7566fdc1e2...)  
**Machine:** 12th Gen Intel(R) Core(TM) i5-12450H, 12 cores, openjdk version "25.0.4" 2026-07-21 LTS

## Headline

| Metric | Value |
| --- | ---: |
| Vault after 8 snapshots | **70.70 MB** |
| Full working trees | 563.44 MB |
| Vault / full trees | **12.55%** |
| Git repository on disk | 366.30 MB |
| Vault / git repository | **19.30%** |
| Vault / last full snapshot | 1.223x |
| Median append per snapshot | 2.52 MB |
| Largest append | 26.81 MB |
| Round-trip failures | 0 |
| Skipped records | 0 |

## Findings

* Vault after 8 restore points: **70.70 MB** (12.55% of 563.44 MB of working trees, 19.30% of the git repository, 1.22x one full snapshot).
* Baseline: 19.21 MB (27.2% of the vault); the other 7 snapshots added 51.49 MB.
* Median append after the baseline: 2.52 MB (4.35% of a full snapshot). Largest: snapshot 2 (00002-20240313-204147-43a3406) at 26.81 MB.
* Smallest vault: zstd L9 / default at 63.85 MB (90.31% of zstd L3 / default).

## Per-snapshot results

| # | Version | Source | World | Targets | New | Chg | Del | Logical | Full | Append | Append/Full | Vault | Time s |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `00001-20240313-182343-faf07dd` | 29.71 MB | 29.71 MB | 4,294 | 0 | 0 | 0 | 125.02 MB | 19.21 MB | 19.21 MB | 100.00% | 19.21 MB | 3.16 |
| 2 | `00002-20240313-204147-43a3406` | 62.74 MB | 62.74 MB | 8,068 | 3,814 | 4,182 | 40 | 297.41 MB | 43.94 MB | 26.81 MB | 61.01% | 46.02 MB | 9.73 |
| 3 | `00003-20240314-032730-ac30560` | 75.28 MB | 75.28 MB | 9,590 | 1,572 | 7,823 | 50 | 349.04 MB | 51.79 MB | 12.09 MB | 23.34% | 58.10 MB | 12.84 |
| 4 | `00004-20240315-141543-aa3447b` | 77.18 MB | 77.18 MB | 9,757 | 224 | 7,120 | 57 | 358.20 MB | 52.96 MB | 2.52 MB | 4.75% | 60.62 MB | 12.34 |
| 5 | `00005-20240315-154008-6c3a932` | 77.39 MB | 77.39 MB | 9,761 | 57 | 2,322 | 53 | 358.24 MB | 52.98 MB | 315.34 kB | 0.60% | 60.93 MB | 4.85 |
| 6 | `00006-20240316-124205-64ecf04` | 77.62 MB | 77.62 MB | 9,766 | 58 | 6,301 | 53 | 358.32 MB | 52.97 MB | 1.09 MB | 2.06% | 62.02 MB | 15.96 |
| 7 | `00007-20240609-164317-2e3a33d` | 79.02 MB | 79.02 MB | 9,965 | 231 | 5,995 | 32 | 367.03 MB | 54.11 MB | 2.50 MB | 4.62% | 64.52 MB | 10.72 |
| 8 | `00008-20240609-190941-48afa25` | 84.49 MB | 84.49 MB | 10,571 | 649 | 8,537 | 43 | 395.06 MB | 57.81 MB | 6.18 MB | 10.69% | 70.70 MB | 13.99 |

## Codec comparison

| Configuration | First full | Last full | Vault | Vault/copies | Median append | Time s | Failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| zstd L3 / default | 19.21 MB | 57.81 MB | 70.70 MB | 12.55% | 2.52 MB | 83.6 | 0 |
| zstd L9 / default | 17.10 MB | 51.46 MB | 63.85 MB | 11.33% | 2.34 MB | 103.8 | 0 |

## Method and caveats

* Content-hash diff, not write capture: incremental numbers are a lower bound for a server that rewrites unchanged data.
* Only the NBT pipeline is stored; JSON/datapack/config bytes are outside the vault.
* Append-only: no GC, keyframes or compaction.
* 42-byte block headers and the block index cache are charged; filesystem rounding is not.
* Timings are indicative single-run wall clock; byte counts are deterministic.
* Git input: 9 commits, 8 effective; the rest only changed files the engine ignores (docs, logs, session.lock, level.dat_old). Each commit was materialised before scanning; prepare time is excluded from the scan columns.
* Source bytes for a commit are an uncompressed working-tree checkout; the git repository size is packed, so the two baselines measure different things.

The self-contained visual report is `report.html` in this directory.

