# Differential backup benchmark - mc-backups

**Created:** 2026-10-22T16:29:48+0800  
**Snapshots:** 19  
**Configuration:** zstd L3 / default  
**Engine:** `$MINIMAL_BACKUP` (sha256 ef7566fdc1e2...)  
**Machine:** 12th Gen Intel(R) Core(TM) i5-12450H, 12 cores, openjdk version "25.0.4" 2026-07-21 LTS

## Headline

| Metric | Value |
| --- | ---: |
| Vault after 19 snapshots | **114.43 MB** |
| Full copies on disk | 1.94 GB |
| Vault / full copies | **5.89%** |
| Vault / last full snapshot | 1.082x |
| Median append per snapshot | 339.08 kB |
| Largest append | 32.88 MB |
| Round-trip failures | 0 |
| Skipped records | 0 |

## Findings

* Vault after 19 restore points: **114.43 MB** (5.89% of 1.94 GB of full copies, 1.08x one full snapshot).
* Baseline: 74.97 MB (65.5% of the vault); the other 18 snapshots added 39.46 MB.
* Median append after the baseline: 339.08 kB (0.32% of a full snapshot). Largest: snapshot 7 (manual-20261007-165154) at 32.88 MB.
* Smallest vault: zstd L9 / default at 99.77 MB (87.19% of zstd L3 / default).

## Per-snapshot results

| # | Version | Source | World | Targets | New | Chg | Del | Logical | Full | Append | Append/Full | Vault | Time s |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `manual-20260820-224017` | 78.44 MB | 134.29 MB | 25,998 | 0 | 0 | 0 | 686.10 MB | 74.97 MB | 74.97 MB | 100.00% | 74.97 MB | 13.05 |
| 2 | `manual-20260820-224142` | 78.46 MB | 134.31 MB | 25,999 | 1 | 255 | 0 | 686.43 MB | 75.00 MB | 363.71 kB | 0.48% | 75.33 MB | 1.29 |
| 3 | `manual-20260820-224217` | 78.47 MB | 134.31 MB | 25,999 | 0 | 49 | 0 | 686.44 MB | 75.00 MB | 306.18 kB | 0.41% | 75.64 MB | 1.21 |
| 4 | `manual-20260822-214031` | 79.24 MB | 134.47 MB | 26,012 | 15 | 1,801 | 2 | 686.32 MB | 75.06 MB | 651.27 kB | 0.87% | 76.29 MB | 2.42 |
| 5 | `manual-20260822-215113` | 79.25 MB | 134.47 MB | 26,012 | 0 | 788 | 0 | 685.98 MB | 75.04 MB | 409.03 kB | 0.55% | 76.70 MB | 2.07 |
| 6 | `manual-20260822-215211` | 79.25 MB | 134.47 MB | 26,012 | 0 | 786 | 0 | 686.12 MB | 75.04 MB | 408.64 kB | 0.54% | 77.11 MB | 2.08 |
| 7 | `manual-20261007-165154` | 112.86 MB | 201.45 MB | 40,692 | 14,688 | 4,384 | 8 | 991.42 MB | 105.73 MB | 32.88 MB | 31.10% | 109.98 MB | 10.84 |
| 8 | `mc-backup-20261010-130006` | 113.08 MB | 201.60 MB | 40,690 | 5 | 2,291 | 7 | 992.15 MB | 105.77 MB | 736.96 kB | 0.70% | 110.72 MB | 3.50 |
| 9 | `mc-backup-20261010-140005` | 113.09 MB | 201.60 MB | 40,690 | 0 | 199 | 0 | 992.12 MB | 105.77 MB | 335.62 kB | 0.32% | 111.06 MB | 3.08 |
| 10 | `mc-backup-20261010-150009` | 113.09 MB | 201.60 MB | 40,690 | 0 | 199 | 0 | 992.14 MB | 105.77 MB | 336.95 kB | 0.32% | 111.39 MB | 3.05 |
| 11 | `mc-backup-20261010-160005` | 113.10 MB | 201.60 MB | 40,690 | 0 | 199 | 0 | 992.13 MB | 105.77 MB | 336.45 kB | 0.32% | 111.73 MB | 3.01 |
| 12 | `mc-backup-20261010-170009` | 113.10 MB | 201.60 MB | 40,690 | 0 | 196 | 0 | 992.13 MB | 105.77 MB | 336.85 kB | 0.32% | 112.07 MB | 3.04 |
| 13 | `mc-backup-20261010-180010` | 113.10 MB | 201.60 MB | 40,690 | 0 | 197 | 0 | 992.12 MB | 105.77 MB | 335.59 kB | 0.32% | 112.40 MB | 3.00 |
| 14 | `mc-backup-20261010-190008` | 113.10 MB | 201.60 MB | 40,690 | 0 | 197 | 0 | 992.16 MB | 105.78 MB | 339.10 kB | 0.32% | 112.74 MB | 3.02 |
| 15 | `mc-backup-20261010-200005` | 113.09 MB | 201.60 MB | 40,690 | 0 | 197 | 0 | 992.16 MB | 105.78 MB | 339.06 kB | 0.32% | 113.08 MB | 2.98 |
| 16 | `mc-backup-20261010-210008` | 113.10 MB | 201.60 MB | 40,690 | 0 | 197 | 0 | 992.16 MB | 105.78 MB | 339.29 kB | 0.32% | 113.42 MB | 3.02 |
| 17 | `mc-backup-20261010-220010` | 113.08 MB | 201.60 MB | 40,690 | 0 | 197 | 0 | 992.12 MB | 105.77 MB | 334.54 kB | 0.32% | 113.75 MB | 3.01 |
| 18 | `mc-backup-20261010-230008` | 113.08 MB | 201.60 MB | 40,690 | 0 | 196 | 0 | 992.16 MB | 105.78 MB | 340.08 kB | 0.32% | 114.09 MB | 2.98 |
| 19 | `mc-backup-20261011-000005` | 113.09 MB | 201.60 MB | 40,690 | 0 | 197 | 0 | 992.15 MB | 105.77 MB | 335.71 kB | 0.32% | 114.43 MB | 3.01 |

## Codec comparison

| Configuration | First full | Last full | Vault | Vault/copies | Median append | Time s | Failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| zstd L3 / default | 74.97 MB | 105.77 MB | 114.43 MB | 5.89% | 339.08 kB | 69.7 | 0 |
| zstd L3 / long | 74.97 MB | 105.77 MB | 114.42 MB | 5.89% | 303.17 kB | 55.6 | 0 |
| zstd L9 / default | 68.32 MB | 96.55 MB | 99.77 MB | 5.13% | 45.21 kB | 67.1 | 0 |
| zstd L9 / long | 68.32 MB | 96.55 MB | 103.77 MB | 5.34% | 229.21 kB | 68.8 | 0 |

## Method and caveats

* Content-hash diff, not write capture: incremental numbers are a lower bound for a server that rewrites unchanged data.
* Only the NBT pipeline is stored; JSON/datapack/config bytes are outside the vault.
* Append-only: no GC, keyframes or compaction.
* 42-byte block headers and the block index cache are charged; filesystem rounding is not.
* Timings are indicative single-run wall clock; byte counts are deterministic.

The self-contained visual report is `report.html` in this directory.

