# Differential backup benchmark - DesperateDino_World

**Created:** 2026-10-22T18:41:29+0800  
**Snapshots:** 34  
**Repository:** https://github.com/DesperateDinosaur/DesperateDino_World at main  
**Commits:** 41 total, 34 effective, 7 skipped  
**Configuration:** zstd L3 / default  
**Engine:** `$MINIMAL_BACKUP` (sha256 ef7566fdc1e2...)  
**Machine:** 12th Gen Intel(R) Core(TM) i5-12450H, 12 cores, openjdk version "25.0.4" 2026-07-21 LTS

## Headline

| Metric | Value |
| --- | ---: |
| Vault after 34 snapshots | **1.89 GB** |
| Full working trees | 56.38 GB |
| Vault / full trees | **3.36%** |
| Git repository on disk | 2.66 GB |
| Vault / git repository | **71.14%** |
| Vault / last full snapshot | 1.853x |
| Median append per snapshot | 1.19 MB |
| Largest append | 815.70 MB |
| Round-trip failures | 0 |
| Skipped records | 0 |

## Findings

* Vault after 34 restore points: **1.89 GB** (3.36% of 56.38 GB of working trees, 71.14% of the git repository, 1.85x one full snapshot).
* Baseline: 802.77 MB (42.4% of the vault); the other 33 snapshots added 1.09 GB.
* Median append after the baseline: 1.19 MB (0.12% of a full snapshot). Largest: snapshot 2 (00002-20260104-062213-83f5e9d) at 815.70 MB.

## Per-snapshot results

| # | Version | Source | World | Targets | New | Chg | Del | Logical | Full | Append | Append/Full | Vault | Time s |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `00001-20260101-202937-7cb73eb` | 1.25 GB | 1.25 GB | 178,711 | 0 | 0 | 0 | 5.16 GB | 802.77 MB | 802.77 MB | 100.00% | 802.77 MB | 114.78 |
| 2 | `00002-20260104-062213-83f5e9d` | 2.51 GB | 2.51 GB | 357,460 | 178,749 | 0 | 0 | 10.32 GB | 1.61 GB | 815.70 MB | 50.80% | 1.62 GB | 126.19 |
| 3 | `00003-20260104-064235-a4d1940` | 1.25 GB | 1.25 GB | 178,774 | 327 | 8,056 | 179,013 | 5.16 GB | 802.94 MB | 14.38 MB | 1.79% | 1.63 GB | 30.10 |
| 4 | `00004-20260109-030734-9b876ed` | 1.35 GB | 1.35 GB | 192,988 | 14,770 | 13,597 | 556 | 5.53 GB | 859.92 MB | 61.13 MB | 7.11% | 1.69 GB | 30.79 |
| 5 | `00005-20260111-022541-87982da` | 1.36 GB | 1.36 GB | 195,210 | 2,611 | 13,790 | 389 | 5.57 GB | 865.35 MB | 8.03 MB | 0.93% | 1.70 GB | 29.77 |
| 6 | `00006-20260111-050821-ec2ba7a` | 1.48 GB | 1.48 GB | 224,099 | 29,032 | 4,277 | 143 | 5.85 GB | 886.59 MB | 23.93 MB | 2.70% | 1.73 GB | 15.38 |
| 7 | `00007-20260112-055741-371243a` | 1.48 GB | 1.48 GB | 224,068 | 489 | 10,695 | 520 | 5.85 GB | 886.58 MB | 1.87 MB | 0.21% | 1.73 GB | 21.03 |
| 8 | `00008-20260112-230047-9aef6d3` | 1.48 GB | 1.48 GB | 224,087 | 143 | 3,977 | 124 | 5.85 GB | 886.59 MB | 572.25 kB | 0.06% | 1.73 GB | 8.56 |
| 9 | `00009-20260116-012928-bc1718a` | 1.56 GB | 1.56 GB | 235,930 | 12,664 | 29,778 | 821 | 6.15 GB | 937.52 MB | 57.47 MB | 6.13% | 1.79 GB | 54.65 |
| 10 | `00010-20260116-063931-23b9d7d` | 1.56 GB | 1.56 GB | 235,933 | 68 | 2,804 | 65 | 6.15 GB | 937.52 MB | 397.18 kB | 0.04% | 1.79 GB | 6.29 |
| 11 | `00011-20260117-100326-6e12c8b` | 1.56 GB | 1.56 GB | 236,286 | 753 | 11,256 | 400 | 6.15 GB | 938.05 MB | 2.27 MB | 0.24% | 1.79 GB | 14.91 |
| 12 | `00012-20260118-100401-d71761c` | 1.63 GB | 1.63 GB | 247,826 | 11,916 | 16,038 | 376 | 6.40 GB | 976.23 MB | 42.50 MB | 4.35% | 1.83 GB | 29.83 |
| 13 | `00013-20260119-100336-32c474e` | 1.66 GB | 1.66 GB | 254,153 | 6,591 | 11,970 | 264 | 6.44 GB | 980.06 MB | 5.92 MB | 0.60% | 1.84 GB | 18.80 |
| 14 | `00014-20260120-100337-b9eca2d` | 1.66 GB | 1.66 GB | 254,353 | 367 | 6,448 | 167 | 6.45 GB | 981.42 MB | 2.61 MB | 0.27% | 1.84 GB | 8.92 |
| 15 | `00015-20260121-100359-22798a7` | 1.71 GB | 1.71 GB | 263,180 | 8,930 | 3,908 | 103 | 6.65 GB | 1.01 GB | 30.51 MB | 3.02% | 1.87 GB | 12.23 |
| 16 | `00016-20260122-100342-caaab16` | 1.71 GB | 1.71 GB | 263,163 | 117 | 3,467 | 134 | 6.65 GB | 1.01 GB | 540.19 kB | 0.05% | 1.87 GB | 8.26 |
| 17 | `00017-20260123-100401-5912253` | 1.73 GB | 1.73 GB | 265,138 | 2,198 | 10,626 | 223 | 6.70 GB | 1.02 GB | 10.19 MB | 1.00% | 1.88 GB | 23.47 |
| 18 | `00018-20260124-100400-95aa0e6` | 1.73 GB | 1.73 GB | 265,736 | 891 | 7,939 | 293 | 6.71 GB | 1.02 GB | 4.01 MB | 0.39% | 1.88 GB | 11.16 |
| 19 | `00019-20260125-100349-aae6e85` | 1.73 GB | 1.73 GB | 265,751 | 65 | 1,135 | 50 | 6.71 GB | 1.02 GB | 194.70 kB | 0.02% | 1.88 GB | 3.62 |
| 20 | `00020-20260130-100339-ab712c5` | 1.73 GB | 1.73 GB | 265,732 | 66 | 2,324 | 85 | 6.71 GB | 1.02 GB | 336.71 kB | 0.03% | 1.89 GB | 5.11 |
| 21 | `00021-20260131-100340-e083d7d` | 1.73 GB | 1.73 GB | 265,766 | 77 | 2,497 | 43 | 6.71 GB | 1.02 GB | 364.92 kB | 0.04% | 1.89 GB | 5.86 |
| 22 | `00022-20260201-100344-46de22e` | 1.73 GB | 1.73 GB | 265,746 | 333 | 8,551 | 353 | 6.71 GB | 1.02 GB | 1.45 MB | 0.14% | 1.89 GB | 17.98 |
| 23 | `00023-20260206-054356-6a0ab5b` | 1.73 GB | 1.73 GB | 265,708 | 273 | 8,039 | 311 | 6.71 GB | 1.02 GB | 1.19 MB | 0.12% | 1.89 GB | 15.78 |
| 24 | `00024-20260207-100359-351fd06` | 1.73 GB | 1.73 GB | 265,851 | 437 | 7,864 | 294 | 6.72 GB | 1.02 GB | 2.18 MB | 0.21% | 1.89 GB | 13.42 |
| 25 | `00025-20260208-100403-e59bdc6` | 1.73 GB | 1.73 GB | 265,838 | 246 | 6,044 | 259 | 6.72 GB | 1.02 GB | 957.66 kB | 0.09% | 1.89 GB | 10.76 |
| 26 | `00026-20260209-100324-b3b2592` | 1.73 GB | 1.73 GB | 265,805 | 139 | 4,383 | 172 | 6.72 GB | 1.02 GB | 634.72 kB | 0.06% | 1.89 GB | 6.93 |
| 27 | `00027-20260217-100338-f450395` | 1.73 GB | 1.73 GB | 265,815 | 35 | 1,003 | 25 | 6.72 GB | 1.02 GB | 152.75 kB | 0.01% | 1.89 GB | 3.09 |
| 28 | `00028-20260328-090334-4833e2e` | 1.73 GB | 1.73 GB | 265,822 | 79 | 2,564 | 72 | 6.72 GB | 1.02 GB | 340.63 kB | 0.03% | 1.89 GB | 6.03 |
| 29 | `00029-20260403-090330-0f98615` | 1.73 GB | 1.73 GB | 265,824 | 17 | 579 | 15 | 6.72 GB | 1.02 GB | 80.78 kB | 0.01% | 1.89 GB | 2.34 |
| 30 | `00030-20260418-090331-5fd2dfb` | 1.73 GB | 1.73 GB | 265,822 | 39 | 713 | 41 | 6.72 GB | 1.02 GB | 129.33 kB | 0.01% | 1.89 GB | 2.60 |
| 31 | `00031-20260511-090313-6252c95` | 1.73 GB | 1.73 GB | 265,820 | 16 | 483 | 18 | 6.72 GB | 1.02 GB | 72.91 kB | 0.01% | 1.89 GB | 2.15 |
| 32 | `00032-20260725-090328-d4c0d4b` | 1.73 GB | 1.73 GB | 265,865 | 47 | 639 | 2 | 6.72 GB | 1.02 GB | 113.66 kB | 0.01% | 1.89 GB | 1.88 |
| 33 | `00033-20260726-090408-4af02ff` | 1.73 GB | 1.73 GB | 265,834 | 96 | 4,039 | 127 | 6.72 GB | 1.02 GB | 548.12 kB | 0.05% | 1.89 GB | 8.82 |
| 34 | `00034-20260728-090335-e0153d8` | 1.73 GB | 1.73 GB | 265,829 | 56 | 1,449 | 61 | 6.72 GB | 1.02 GB | 219.19 kB | 0.02% | 1.89 GB | 4.56 |

## Method and caveats

* Content-hash diff, not write capture: incremental numbers are a lower bound for a server that rewrites unchanged data.
* Only the NBT pipeline is stored; JSON/datapack/config bytes are outside the vault.
* Append-only: no GC, keyframes or compaction.
* 42-byte block headers and the block index cache are charged; filesystem rounding is not.
* Timings are indicative single-run wall clock; byte counts are deterministic.
* Git input: 41 commits, 34 effective; the rest only changed files the engine ignores (docs, logs, session.lock, level.dat_old). Each commit was materialised before scanning; prepare time is excluded from the scan columns.
* Source bytes for a commit are an uncompressed working-tree checkout; the git repository size is packed, so the two baselines measure different things.

The self-contained visual report is `report.html` in this directory.

