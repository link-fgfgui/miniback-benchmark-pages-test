#!/usr/bin/env python3
"""Build a GitHub-Pages-friendly copy of a results directory.

The working results contain full change logs (hundreds of MB) and local paths in logs and
command lines. This script copies only what the reports need, gzips oversized change logs,
sanitises local paths, regenerates every report against the published files, and writes the
index/overview landing pages.

    tools/build_site.py --results /data/bench/results --out results
"""
from __future__ import annotations

import argparse
import json
import lzma
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
KEEP = ("versions.csv", "families.csv", "regions.csv", "skipped.csv")
PATH_MAP = (
    ("/home/link/Documents/mcmoddev/miniback-benchmark", "$PROJECT"),
    ("/home/link/Documents/mcmoddev/minimal-backup", "$MINIMAL_BACKUP"),
    ("/run/media/link/F0D66DC87F238D7E/test-miniback", "$BENCH_BASE"),
)


def sanitize(text: str) -> str:
    for old, new in PATH_MAP:
        text = text.replace(old, new)
    return text


def sanitize_json(value):
    if isinstance(value, str):
        return sanitize(value)
    if isinstance(value, list):
        return [sanitize_json(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_json(item) for key, item in value.items()}
    return value


def write_changes(source: Path, run_dir: Path, threshold: int) -> None:
    if source.stat().st_size <= threshold:
        shutil.copy2(source, run_dir / "changes.csv")
        return
    with source.open("rb") as src, lzma.open(run_dir / "changes.csv.xz", "wb",
                                             preset=6) as dst:
        shutil.copyfileobj(src, dst, length=1 << 20)


def build(src: Path, out: Path, threshold: int) -> None:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    studies = []
    for study_dir in sorted(src.iterdir()):
        study_path = study_dir / "study.json"
        if not study_dir.is_dir() or not study_path.is_file():
            continue
        study = json.loads(study_path.read_text(encoding="utf-8"))
        if not study.get("runs"):
            continue
        studies.append(study_dir.name)
        dest = out / study_dir.name
        dest.mkdir()
        study = sanitize_json(study)
        (dest / "study.json").write_text(json.dumps(study, indent=2), encoding="utf-8")
        for run in study["runs"]:
            run_dir = dest / run.get("dir", run["id"])
            run_dir.mkdir(parents=True, exist_ok=True)
            source_run = study_dir / run.get("dir", run["id"])
            for name in KEEP:
                if (source_run / name).is_file():
                    shutil.copy2(source_run / name, run_dir / name)
            changes = source_run / "changes.csv"
            if changes.is_file():
                write_changes(changes, run_dir, threshold)
        subprocess.run([sys.executable, str(HERE / "report.py"), str(dest)], check=True)
        for name in ("report.html", "report.md"):
            path = dest / name
            if path.is_file():
                path.write_text(sanitize(path.read_text(encoding="utf-8")), encoding="utf-8")
        print(f"[site] {study_dir.name}", flush=True)
    if not studies:
        raise SystemExit(f"no studies under {src}")
    subprocess.run([sys.executable, str(HERE / "overview.py"), str(out)], check=True)
    (out / ".nojekyll").write_text("", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", required=True)
    parser.add_argument("--out", default=str(PROJECT / "results"))
    parser.add_argument("--max-changes-mb", type=int, default=20)
    args = parser.parse_args(argv)
    build(Path(args.results).resolve(), Path(args.out).resolve(),
          args.max_changes_mb * 1_000_000)
    return 0


if __name__ == "__main__":
    sys.exit(main())
