# Differential backup benchmark - Minecraft_World_Backup

**Created:** 2026-10-22T18:13:18+0800  
**Snapshots:** 21  
**Repository:** https://github.com/Shubhamjoshidev-28/Minecraft_World_Backup at master  
**Commits:** 27 total, 21 effective, 6 skipped  
**Configuration:** zstd L3 / default  
**Engine:** `$MINIMAL_BACKUP` (sha256 ef7566fdc1e2...)  
**Machine:** 12th Gen Intel(R) Core(TM) i5-12450H, 12 cores, openjdk version "25.0.4" 2026-07-21 LTS

## Headline

| Metric | Value |
| --- | ---: |
| Vault after 21 snapshots | **183.71 MB** |
| Full working trees | 4.10 GB |
| Vault / full trees | **4.48%** |
| Git repository on disk | 1.11 GB |
| Vault / git repository | **16.49%** |
| Vault / last full snapshot | 1.137x |
| Median append per snapshot | 2.93 MB |
| Largest append | 53.17 MB |
| Round-trip failures | 0 |
| Skipped records | 0 |

## Findings

* Vault after 21 restore points: **183.71 MB** (4.48% of 4.10 GB of working trees, 16.49% of the git repository, 1.14x one full snapshot).
* Baseline: 55.58 MB (30.3% of the vault); the other 20 snapshots added 128.13 MB.
* Median append after the baseline: 2.93 MB (1.82% of a full snapshot). Largest: snapshot 9 (00009-20260623-133440-f7dcca0) at 53.17 MB.
* Smallest vault: zstd L9 / default at 166.33 MB (90.54% of zstd L3 / default).

## Per-snapshot results

| # | Version | Source | World | Targets | New | Chg | Del | Logical | Full | Append | Append/Full | Vault | Time s |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `00001-20260611-175401-4ebc2b7` | 96.71 MB | 96.71 MB | 14,770 | 0 | 0 | 0 | 363.76 MB | 55.58 MB | 55.58 MB | 100.00% | 55.58 MB | 10.82 |
| 2 | `00002-20260619-075159-0c5a6af` | 96.78 MB | 96.78 MB | 14,759 | 52 | 1,739 | 63 | 364.07 MB | 55.61 MB | 296.26 kB | 0.53% | 55.88 MB | 4.21 |
| 3 | `00003-20260620-202014-9fd067d` | 100.69 MB | 100.69 MB | 15,244 | 609 | 5,359 | 124 | 379.99 MB | 58.08 MB | 3.66 MB | 6.30% | 59.54 MB | 8.30 |
| 4 | `00004-20260621-121913-e8fd2bc` | 103.17 MB | 103.17 MB | 15,575 | 475 | 6,649 | 144 | 391.46 MB | 59.77 MB | 3.42 MB | 5.72% | 62.96 MB | 8.19 |
| 5 | `00005-20260621-193221-ff918ca` | 103.25 MB | 103.25 MB | 15,624 | 133 | 3,165 | 84 | 391.64 MB | 59.82 MB | 528.82 kB | 0.88% | 63.48 MB | 5.07 |
| 6 | `00006-20260622-085758-db7817a` | 105.67 MB | 105.67 MB | 15,874 | 414 | 5,756 | 164 | 402.12 MB | 61.53 MB | 3.28 MB | 5.34% | 66.77 MB | 8.38 |
| 7 | `00007-20260622-191731-5fc0f06` | 143.28 MB | 143.28 MB | 22,014 | 6,340 | 7,235 | 200 | 542.53 MB | 82.62 MB | 23.31 MB | 28.21% | 90.08 MB | 12.36 |
| 8 | `00008-20260623-094429-40c51a1` | 146.31 MB | 146.31 MB | 22,524 | 589 | 3,574 | 79 | 553.85 MB | 84.26 MB | 2.58 MB | 3.07% | 92.66 MB | 4.52 |
| 9 | `00009-20260623-133440-f7dcca0` | 222.76 MB | 222.76 MB | 33,078 | 10,629 | 3,340 | 75 | 879.11 MB | 135.75 MB | 53.17 MB | 39.17% | 145.83 MB | 10.48 |
| 10 | `00010-20260624-125249-4dacdb0` | 231.96 MB | 231.96 MB | 34,464 | 1,591 | 6,412 | 205 | 913.31 MB | 140.90 MB | 6.94 MB | 4.93% | 152.78 MB | 10.33 |
| 11 | `00011-20260625-095731-6c9c1e1` | 232.00 MB | 232.00 MB | 34,462 | 107 | 2,841 | 109 | 913.33 MB | 140.90 MB | 481.64 kB | 0.34% | 153.26 MB | 6.34 |
| 12 | `00012-20260626-120134-ee7bf27` | 232.36 MB | 232.36 MB | 34,467 | 140 | 4,235 | 135 | 913.90 MB | 141.00 MB | 887.67 kB | 0.63% | 154.15 MB | 6.97 |
| 13 | `00013-20260627-122307-26dc6ee` | 243.60 MB | 243.60 MB | 35,991 | 1,721 | 7,432 | 197 | 961.01 MB | 148.39 MB | 8.85 MB | 5.97% | 163.00 MB | 10.91 |
| 14 | `00014-20260627-182909-2912e1b` | 243.61 MB | 243.61 MB | 36,015 | 72 | 1,650 | 48 | 961.06 MB | 148.40 MB | 286.62 kB | 0.19% | 163.29 MB | 3.13 |
| 15 | `00015-20260628-092127-b86f1af` | 243.62 MB | 243.62 MB | 36,028 | 74 | 1,332 | 61 | 961.16 MB | 148.43 MB | 274.81 kB | 0.19% | 163.56 MB | 2.53 |
| 16 | `00016-20260628-191146-71184e2` | 252.80 MB | 252.80 MB | 37,299 | 1,421 | 5,979 | 150 | 1.00 GB | 154.84 MB | 8.25 MB | 5.33% | 171.81 MB | 10.13 |
| 17 | `00017-20260629-192115-e226393` | 257.72 MB | 257.72 MB | 37,727 | 633 | 8,014 | 205 | 1.02 GB | 158.54 MB | 5.94 MB | 3.75% | 177.75 MB | 11.77 |
| 18 | `00018-20260702-091011-61dceec` | 257.90 MB | 257.90 MB | 37,718 | 206 | 5,906 | 215 | 1.02 GB | 158.62 MB | 1.10 MB | 0.69% | 178.85 MB | 9.48 |
| 19 | `00019-20260703-113533-7f7dd43` | 257.94 MB | 257.94 MB | 37,723 | 92 | 2,008 | 87 | 1.02 GB | 158.64 MB | 388.28 kB | 0.24% | 179.24 MB | 3.83 |
| 20 | `00020-20260711-173537-223b1de` | 263.11 MB | 263.11 MB | 38,626 | 1,063 | 6,201 | 160 | 1.04 GB | 161.59 MB | 4.32 MB | 2.67% | 183.56 MB | 9.17 |
| 21 | `00021-20260919-140323-980c611` | 263.15 MB | 263.15 MB | 38,679 | 67 | 729 | 14 | 1.04 GB | 161.64 MB | 152.60 kB | 0.09% | 183.71 MB | 1.46 |

## Codec comparison

| Configuration | First full | Last full | Vault | Vault/copies | Median append | Time s | Failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| zstd L3 / default | 55.58 MB | 161.64 MB | 183.71 MB | 4.48% | 2.93 MB | 158.4 | 0 |
| zstd L9 / default | 50.06 MB | 145.30 MB | 166.33 MB | 4.06% | 2.68 MB | 196.4 | 0 |

## Method and caveats

* Content-hash diff, not write capture: incremental numbers are a lower bound for a server that rewrites unchanged data.
* Only the NBT pipeline is stored; JSON/datapack/config bytes are outside the vault.
* Append-only: no GC, keyframes or compaction.
* 42-byte block headers and the block index cache are charged; filesystem rounding is not.
* Timings are indicative single-run wall clock; byte counts are deterministic.
* Git input: 27 commits, 21 effective; the rest only changed files the engine ignores (docs, logs, session.lock, level.dat_old). Each commit was materialised before scanning; prepare time is excluded from the scan columns.
* Source bytes for a commit are an uncompressed working-tree checkout; the git repository size is packed, so the two baselines measure different things.

The self-contained visual report is `report.html` in this directory.

