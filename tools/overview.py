#!/usr/bin/env python3
"""Summarise every git-backed study in a results directory into overview.html/md."""
from __future__ import annotations

import csv
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import report  # noqa: E402  (local module)


def load(study_dir: Path) -> dict | None:
    path = study_dir / "study.json"
    if not path.is_file():
        return None
    study = json.loads(path.read_text(encoding="utf-8"))
    dataset = study.get("dataset", {})
    kind = dataset.get("kind")
    if kind not in ("git", "archive"):
        kind = "archive" if dataset.get("total_source_bytes") else "git"
    baseline = report.num(dataset.get("repo_bytes") or dataset.get("total_source_bytes"))
    runs = study.get("runs", [])
    if not runs:
        return None
    primary = runs[0]
    run_dir = study_dir / primary.get("dir", primary["id"])
    versions_path = run_dir / "versions.csv"
    if not versions_path.is_file():
        return None
    with versions_path.open(encoding="utf-8", newline="") as handle:
        versions = list(csv.DictReader(handle))
    if not versions:
        return None
    incr = [report.num(row.get("actual_incr_total", row.get("incr_total"))) for row in versions]
    later = incr[1:]
    vault = report.num(versions[-1].get("actual_cumulative_min",
                                        versions[-1].get("cumulative_min")))
    return {
        "name": study_dir.name,
        "kind": kind,
        "repo": dataset.get("repo", study_dir.name),
        "branch": dataset.get("branch", ""),
        "total": int(dataset.get("commits_total") or len(versions)),
        "effective": int(dataset.get("commits_effective") or len(versions)),
        "skipped": int(dataset.get("commits_skipped", 0)),
        "snapshots": len(versions),
        "world": report.num(versions[-1].get("world_bytes")),
        "source": report.num(versions[-1].get("cumulative_source")),
        "repo_bytes": baseline,
        "vault": vault,
        "median": statistics.median(later) if later else 0,
        "time": sum(report.num(row.get("total_ms")) for row in versions) / 1000,
        "failures": sum(report.num(row.get("roundtrip_fail")) for row in versions),
        "first": dataset.get("first_date", ""),
        "last": dataset.get("last_date", ""),
        "config": primary.get("id", ""),
    }


def main(argv: list[str]) -> int:
    results = Path(argv[1]).resolve() if len(argv) > 1 else (HERE.parent / "results")
    studies = [item for item in (load(path) for path in sorted(results.iterdir())
                                 if path.is_dir()) if item]
    if not studies:
        raise SystemExit(f"no git studies under {results}")

    total_vault = sum(s["vault"] for s in studies)
    total_baseline = sum(s["repo_bytes"] for s in studies)
    total_commits = sum(s["effective"] for s in studies)
    total_fail = sum(s["failures"] for s in studies)
    git_count = sum(1 for s in studies if s["kind"] == "git")
    archive_count = len(studies) - git_count

    kpis = "".join([
        report.kpi("Datasets", str(len(studies)),
                   f"{git_count} git + {archive_count} archive", "big"),
        report.kpi("Effective commits", f"{total_commits:,}",
                   "restore points benchmarked"),
        report.kpi("Combined vault", report.mb(total_vault), "one vault per dataset"),
        report.kpi("Combined baseline", report.mb(total_baseline),
                   "git packs + archive sets"),
        report.kpi("Vault / baseline", report.pct(total_vault, total_baseline),
                   f"{total_baseline / total_vault:.2f}x smaller" if total_vault else "n/a",
                   "good"),
        report.kpi("Correctness", f"{int(total_fail)} failures",
                   "all blocks round-tripped" if total_fail == 0 else "not trustworthy",
                   "good" if total_fail == 0 else "bad"),
    ])

    rows = []
    for s in studies:
        rows.append([
            f'<a href="{report.esc(s["name"])}/report.html">{report.esc(s["name"])}</a>',
            "git" if s["kind"] == "git" else "archive",
            f'{s["effective"]:,} / {s["total"]:,}',
            report.mb(s["repo_bytes"]),
            report.mb(s["vault"]),
            report.pct(s["vault"], s["repo_bytes"]),
            f'{s["failures"]:.0f}',
        ])
    table = report.render_table(
        ["Study", "Type", "Effective / total", "Baseline", "Vault", "Vault / baseline",
         "Failures"],
        rows, numeric_from=2)

    labels = [s["name"] for s in studies]
    chart = report.bar_chart(
        labels,
        [
            {"name": "Baseline store", "color": report.PURPLE,
             "values": [report.mb_num(s["repo_bytes"]) for s in studies]},
            {"name": "Engine vault", "color": report.ACCENT,
             "values": [report.mb_num(s["vault"]) for s in studies]},
        ],
        y_fmt=lambda v: f"{v:,.0f}", y_title="MB (log scale)", log=True, height=380)

    ratio_chart = report.bar_chart(
        labels,
        [{"name": "Vault / baseline", "color": report.GREEN,
          "values": [100.0 * s["vault"] / s["repo_bytes"] if s["repo_bytes"] else 0
                     for s in studies]}],
        y_fmt=lambda v: f"{v:.0f}%", y_title="vault as % of the baseline store", height=300)

    body = f"""
<header>
  <div class="eyebrow">minimal-backup / differential storage benchmark</div>
  <h1>World backup benchmark</h1>
  <p class="lede">{git_count} public git repositories and {archive_count} archive set
  ({len(studies)} datasets) replayed through the engine's checkpoint policy. The vault is
  compared with the store that already holds the same history: packed git repositories or the
  original compressed save archives.</p>
</header>
<div class="kpis">{kpis}</div>
{report.card("Vault versus baseline", chart,
             "Log scale. The baseline is the packed git repository or the archive set that "
             "already holds the same saves. The engine stores canonical NBT blocks with its own "
             "delta coder. Lower is better.")}
{report.card("Vault as a share of baseline", ratio_chart,
             "Below 100% means the engine's vault is smaller than the store holding the same "
             "history.")}
{report.card("Per-dataset results", table,
             "Effective commits change at least one tracked world file; documentation-only "
             "commits are skipped exactly as the engine ignores them. Open a study name for its "
             "full visual report.")}
<footer>Generated by <code>tools/overview.py</code>. All charts are inline SVG.</footer>
"""
    css_text = """
:root{color-scheme:light}
*{box-sizing:border-box}
body{margin:0;background:#f7f9fc;color:#1b2430;font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:36px 28px 64px}
header{padding:14px 0 28px;border-bottom:1px solid #e3e9f0;margin-bottom:26px}
.eyebrow{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#2f6df6;font-weight:650}
h1{font-size:34px;line-height:1.15;margin:8px 0 6px;letter-spacing:-.02em}
.lede{max-width:820px;color:#4d5a6b;margin:0 0 16px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:12px;margin-bottom:18px}
.kpi{background:#fff;border:1px solid #e3e9f0;border-radius:12px;padding:14px 16px}
.kpi-label{font-size:11.5px;letter-spacing:.04em;text-transform:uppercase;color:#6c7888;font-weight:600}
.kpi-value{font:600 24px/1.3 ui-monospace,SFMono-Regular,Menlo,monospace;margin-top:3px}
.kpi-note{font-size:12px;color:#7a8797;margin-top:2px}
.kpi.big .kpi-value{color:#2f6df6}.kpi.good .kpi-value{color:#0f9d68}.kpi.bad .kpi-value{color:#d93a41}
.card{background:#fff;border:1px solid #e3e9f0;border-radius:14px;padding:20px 22px 18px;margin:0 0 18px;overflow:hidden}
.card h2{font-size:16px;margin:0 0 4px}
.card .note{color:#6c7888;font-size:12.5px;margin:8px 0 0;max-width:900px}
.table-wrap{overflow:auto;margin-top:12px;border:1px solid #edf1f6;border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:12.5px}
th,td{padding:7px 9px;border-bottom:1px solid #edf1f6;white-space:nowrap}
th{position:sticky;top:0;background:#f9fbfe;font-weight:650;color:#4d5a6b;text-align:left}
td.num,th.num{text-align:right;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
tbody tr:hover{background:#f7faff}
a{color:#2f6df6;text-decoration:none}a:hover{text-decoration:underline}
footer{color:#7a8797;font-size:12px;margin-top:28px;padding-top:16px;border-top:1px solid #e3e9f0}
@media print{body{background:#fff}.card{break-inside:avoid}}
"""
    doc = ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
           "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
           "<title>Git world backup benchmark</title>"
           f"<style>{css_text}</style></head><body><div class=\"wrap\">{body}</div></body></html>")
    (results / "overview.html").write_text(doc, encoding="utf-8")

    md = ["# World backup benchmark - overview", ""]
    md.append(f"**Datasets:** {len(studies)} ({git_count} git, {archive_count} archive)  ")
    md.append(f"**Effective commits:** {total_commits:,}  ")
    md.append(f"**Combined vault:** {report.mb(total_vault)}  ")
    md.append(f"**Combined baseline:** {report.mb(total_baseline)}  ")
    md.append(f"**Vault / baseline:** {report.pct(total_vault, total_baseline)}  ")
    md.append("")
    md.append("| Study | Type | Effective / total | Snapshots | World (last) | Baseline | "
              "Vault | Vault / baseline | Median append | Failures |")
    md.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for s in studies:
        md.append(f"| [{s['name']}]({s['name']}/report.html) | {s['kind']} | "
                  f"{s['effective']} / {s['total']} | {s['snapshots']} | "
                  f"{report.mb(s['world'])} | {report.mb(s['repo_bytes'])} | "
                  f"{report.mb(s['vault'])} | {report.pct(s['vault'], s['repo_bytes'])} | "
                  f"{report.mb(s['median'])} | {int(s['failures'])} |")
    md.append("")
    (results / "overview.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    # Landing page for GitHub Pages. It links the original project and the overview.
    cards = []
    for s in studies:
        ratio = 100.0 * s["vault"] / s["repo_bytes"] if s["repo_bytes"] else 0.0
        kind = "git" if s["kind"] == "git" else "archive"
        repo = s["repo"].replace("https://github.com/", "")
        cards.append(f"""
<a class="study" href="{report.esc(s['name'])}/report.html">
  <div class="study-top"><span class="badge {kind}">{kind}</span>
    <span class="study-name">{report.esc(s['name'])}</span></div>
  <div class="study-repo">{report.esc(repo)}</div>
  <div class="study-stats">
    <div><b>{s['effective']:,}</b><span>effective commits</span></div>
    <div><b>{report.mb(s['vault'])}</b><span>vault</span></div>
    <div><b>{ratio:.1f}%</b><span>of baseline</span></div>
  </div>
  <div class="meter"><i style="width:{min(100.0, ratio):.1f}%"></i></div>
  <div class="open">Open report →</div>
</a>""")
    index_css = """
:root{color-scheme:light}
*{box-sizing:border-box}
body{margin:0;background:#f7f9fc;color:#1b2430;font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:40px 28px 64px}
header{padding:8px 0 26px;border-bottom:1px solid #e3e9f0;margin-bottom:22px}
.eyebrow{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#2f6df6;font-weight:650}
h1{font-size:38px;line-height:1.12;margin:8px 0 8px;letter-spacing:-.025em}
.lede{max-width:820px;color:#4d5a6b;margin:0 0 18px}
.actions{display:flex;flex-wrap:wrap;gap:10px}
.actions a{border-radius:999px;padding:8px 16px;font-size:13.5px;font-weight:600;text-decoration:none;border:1px solid #2f6df6}
.actions .primary{background:#2f6df6;color:#fff}
.actions .ghost{background:#fff;color:#2f6df6}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:18px 0 22px}
.kpi{background:#fff;border:1px solid #e3e9f0;border-radius:12px;padding:13px 15px}
.kpi b{display:block;font:600 22px/1.3 ui-monospace,SFMono-Regular,Menlo,monospace}
.kpi span{font-size:11.5px;letter-spacing:.04em;text-transform:uppercase;color:#6c7888;font-weight:600}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}
.study{display:block;background:#fff;border:1px solid #e3e9f0;border-radius:14px;padding:16px 18px 14px;text-decoration:none;color:inherit;transition:border-color .15s,transform .15s}
.study:hover{border-color:#9db4dc;transform:translateY(-1px)}
.study-top{display:flex;align-items:center;gap:8px}
.badge{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;padding:2px 7px;border-radius:999px;font-weight:700}
.badge.git{background:#e8efff;color:#2f6df6}
.badge.archive{background:#fff2dd;color:#a96600}
.study-name{font-weight:650;font-size:14.5px}
.study-repo{font:11.5px ui-monospace,SFMono-Regular,Menlo,monospace;color:#7a8797;margin:5px 0 10px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.study-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}
.study-stats b{display:block;font:600 15px/1.3 ui-monospace,SFMono-Regular,Menlo,monospace}
.study-stats span{font-size:11px;color:#7a8797}
.meter{height:6px;background:#eef2f7;border-radius:999px;margin:11px 0 9px;overflow:hidden}
.meter i{display:block;height:100%;background:#2f6df6;border-radius:999px}
.open{font-size:12.5px;color:#2f6df6;font-weight:600}
.method{background:#fff;border:1px solid #e3e9f0;border-radius:14px;padding:18px 20px;margin-top:18px;color:#3c4a5b;font-size:13.5px}
.method h2{font-size:16px;color:#1b2430;margin:0 0 6px}
.method p{margin:6px 0;max-width:980px}
footer{color:#7a8797;font-size:12px;margin-top:26px;padding-top:14px;border-top:1px solid #e3e9f0}
code{font:12.5px ui-monospace,SFMono-Regular,Menlo,monospace;background:#f1f5fa;padding:1px 5px;border-radius:4px}
@media print{body{background:#fff}.study{break-inside:avoid}}
"""
    index_doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>minimal-backup · world backup benchmark</title><style>{index_css}</style></head>
<body><div class="wrap">
<header>
  <div class="eyebrow">minimal-backup / differential storage benchmark</div>
  <h1>World backups, measured.</h1>
  <p class="lede">Every effective commit from {git_count} public git repositories and
  {archive_count} archive set was replayed through the engine's checkpoint policy. The vault is
  compared with the store that already holds the same history.</p>
  <div class="actions">
    <a class="primary" href="overview.html">Open the full overview</a>
    <a class="ghost" href="https://github.com/link-fgfgui/minimal-backup">Original project on GitHub</a>
  </div>
</header>
<div class="kpis">
  <div class="kpi"><b>{len(studies)}</b><span>datasets</span></div>
  <div class="kpi"><b>{total_commits:,}</b><span>effective commits</span></div>
  <div class="kpi"><b>{report.mb(total_vault)}</b><span>combined vault</span></div>
  <div class="kpi"><b>{report.mb(total_baseline)}</b><span>combined baseline</span></div>
  <div class="kpi"><b>{report.pct(total_vault, total_baseline)}</b><span>vault / baseline</span></div>
</div>
<section class="grid">{''.join(cards)}</section>
<section class="method"><h2>What is measured</h2>
<p>Only commits that change a file the engine tracks are replayed: <code>.mca</code> chunks,
<code>level.dat</code>, <code>playerdata/*.dat</code> and <code>data/**/*.dat</code>. Commits
that only touch documentation, logs, <code>session.lock</code> or <code>level.dat_old</code> are
skipped. Every FULL and DELTA block is decompressed and byte-compared after writing.</p>
<p>The baseline is the packed git repository or the original compressed archive set. The vault
is the engine's append-only store, including block headers and the block index cache.</p>
</section>
<footer>Generated by <code>tools/overview.py</code>. All pages are self-contained HTML with
inline SVG and CSS.</footer>
</div></body></html>"""
    (results / "index.html").write_text(index_doc, encoding="utf-8")
    (results / ".nojekyll").write_text("", encoding="utf-8")
    print(f"wrote {results / 'index.html'}")
    print(f"wrote {results / 'overview.html'}")
    print(f"wrote {results / 'overview.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
