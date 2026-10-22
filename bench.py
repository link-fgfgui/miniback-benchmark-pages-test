#!/usr/bin/env python3
"""Progressive full-save benchmark for the minimal-backup engine.

Takes a growing series of complete world saves (oldest first), replays them through
the engine's diff policy, and writes a visual report.

    ./bench.py run --saves saves/
    ./bench.py run --saves saves/ --levels 3,9 --long off,on --name demo
    ./bench.py run --zip ../rewind-others/mc-backups.zip --name legacy
    ./bench.py report results/demo

Input layout (--saves DIR), one directory or archive per snapshot:

    saves/
      01-world/            <- a world root, or a directory containing world/
      02-world.tar.gz
      03-world/level.dat   <- also accepted
      ...

Order is natural filename order unless --manifest is given:

    # label <TAB> path <TAB> source-bytes(optional)
    01  /data/saves/01-world  123456789

Only stdlib Python is required. The engine under test is compiled read-only from
--project (default ../minimal-backup).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = Path(os.environ.get("BENCH_RESULTS", HERE / "results")).resolve()
WORK = Path(os.environ.get("BENCH_WORK", HERE / "work")).resolve()
OUT = HERE / "out"
ARCHIVE_SUFFIXES = (".tar.gz", ".tgz", ".tar")
ZIP_SUFFIXES = (".zip",)
SNAPSHOT_SUFFIXES = ARCHIVE_SUFFIXES + ZIP_SUFFIXES
DEFAULT_PROJECT = HERE.parent / "minimal-backup"


def natural_key(name: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def human_ms(ms: float) -> str:
    if ms < 1000:
        return f"{ms:.0f} ms"
    if ms < 60_000:
        return f"{ms / 1000:.1f} s"
    return f"{ms / 60000:.1f} min"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def dir_bytes(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def find_world_root(root: Path) -> Path | None:
    """Locate the world inside a snapshot directory (depth <= 2)."""
    if (root / "level.dat").is_file() or (root / "region").is_dir():
        return root
    best = None
    for depth in (1, 2):
        for candidate in sorted(root.glob("/".join(["*"] * depth))):
            if not candidate.is_dir():
                continue
            if (candidate / "level.dat").is_file():
                score = (candidate.name != "world", len(candidate.relative_to(root).parts),
                         str(candidate))
                if best is None or score < best[0]:
                    best = (score, candidate)
        if best:
            return best[1]
    return None


def extract(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    name = archive.name.lower()
    if name.endswith(ZIP_SUFFIXES):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(dest)
    elif name.endswith(ARCHIVE_SUFFIXES):
        with tarfile.open(archive) as tf:
            tf.extractall(dest, filter="data")
    else:
        raise SystemExit(f"unsupported archive: {archive}")


def extract_cached(source: Path, label: str) -> Path:
    """Extract an archive once into work/extract; reuse if the source is unchanged."""
    key = hashlib.sha1(f"{source.resolve()}|{source.stat().st_size}|"
                       f"{source.stat().st_mtime_ns}".encode()).hexdigest()[:12]
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", label)[:60]
    dest = WORK / "extract" / f"{safe}-{key}"
    marker = dest / ".bench-source"
    stamp = f"{source.resolve()}|{source.stat().st_size}|{source.stat().st_mtime_ns}"
    if marker.is_file() and marker.read_text(encoding="utf-8").strip() == stamp:
        return dest
    if dest.exists():
        shutil.rmtree(dest)
    print(f"[bench] extracting {source.name} -> {dest.relative_to(HERE)}", flush=True)
    extract(source, dest)
    marker.write_text(stamp, encoding="utf-8")
    return dest


def snapshot_from_zip(zip_path: Path) -> list[dict]:
    """Legacy layout: a zip whose members are full-save tar.gz archives."""
    root = WORK / "extract" / f"zip-{sha256_file(zip_path)[:12]}"
    snapshots = []
    with zipfile.ZipFile(zip_path) as zf:
        members = [m for m in zf.namelist()
                   if not m.endswith("/") and m.lower().endswith(ARCHIVE_SUFFIXES)]
        members.sort(key=natural_key)
        sizes = {m: zf.getinfo(m).file_size for m in members}
        if not members:
            raise SystemExit(f"no .tar.gz snapshots inside {zip_path}")
        for member in members:
            label = Path(member).name
            for suffix in ARCHIVE_SUFFIXES:
                if label.lower().endswith(suffix):
                    label = label[: -len(suffix)]
                    break
            dest = root / re.sub(r"[^A-Za-z0-9._-]+", "_", label)[:60]
            marker = dest / ".bench-source"
            stamp = f"{zip_path.resolve()}!{member}"
            if not (marker.is_file() and marker.read_text(encoding="utf-8").strip() == stamp):
                if dest.exists():
                    shutil.rmtree(dest)
                dest.mkdir(parents=True, exist_ok=True)
                print(f"[bench] extracting {member}", flush=True)
                payload = zf.read(member)
                tmp = dest / "_payload.tar.gz"
                tmp.write_bytes(payload)
                with tarfile.open(tmp) as tf:
                    tf.extractall(dest, filter="data")
                tmp.unlink()
                marker.write_text(stamp, encoding="utf-8")
            snapshots.append({"label": label, "root": dest, "source_bytes": sizes[member],
                              "kind": "zip-member"})
    return snapshots


def collect_snapshots(args) -> list[dict]:
    if args.manifest:
        return read_manifest(Path(args.manifest), getattr(args, "raw_manifest", False))
    if args.zip:
        return snapshot_from_zip(Path(args.zip))
    if not args.saves:
        raise SystemExit("give --saves DIR, --zip FILE or --manifest FILE")
    root = Path(args.saves).resolve()
    if not root.is_dir():
        raise SystemExit(f"not a directory: {root}")
    entries = [p for p in root.iterdir() if not p.name.startswith(".")]
    entries.sort(key=lambda p: natural_key(p.name))
    snapshots = []
    for entry in entries:
        if entry.is_dir():
            snapshots.append({"label": entry.name, "root": entry,
                              "source_bytes": dir_bytes(entry), "kind": "dir"})
        elif entry.name.lower().endswith(SNAPSHOT_SUFFIXES):
            snapshots.append({"label": strip_suffix(entry.name), "root": entry,
                              "source_bytes": entry.stat().st_size, "kind": "archive"})
    if args.order == "mtime":
        snapshots.sort(key=lambda s: s["root"].stat().st_mtime)
    if not snapshots:
        raise SystemExit(f"no snapshots found in {root}")
    return snapshots


def strip_suffix(name: str) -> str:
    for suffix in SNAPSHOT_SUFFIXES:
        if name.lower().endswith(suffix):
            return name[: -len(suffix)]
    return name


def read_manifest(path: Path, raw_manifest: bool = False) -> list[dict]:
    snapshots = []
    base = path.parent
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t") if "\t" in line else line.split()
        if len(parts) < 2:
            raise SystemExit(f"bad manifest line: {line}")
        label = parts[0]
        if raw_manifest:
            snapshots.append({
                "label": label,
                "roots": parts[1],
                "source_bytes": int(parts[2]) if len(parts) > 2 and parts[2] else 0,
                "prepare": parts[3] if len(parts) > 3 and parts[3] else None,
                "kind": "engine",
            })
            continue
        source = Path(parts[1])
        if not source.is_absolute():
            source = (base / source).resolve()
        snapshots.append({"label": label, "root": source,
                          "source_bytes": int(parts[2]) if len(parts) > 2 else
                          (dir_bytes(source) if source.is_dir() else source.stat().st_size),
                          "kind": "manifest"})
    return snapshots


def prepare(snapshots: list[dict]) -> list[dict]:
    prepared = []
    seen = set()
    for snap in snapshots:
        label = snap["label"]
        if label in seen:
            raise SystemExit(f"duplicate snapshot label: {label}")
        seen.add(label)
        if snap.get("kind") == "engine":
            snap = dict(snap)
            snap["source_bytes"] = int(snap.get("source_bytes") or 0)
            prepared.append(snap)
            continue
        source = snap["root"]
        if source.is_file():
            source = extract_cached(source, label)
        if not source.is_dir():
            raise SystemExit(f"snapshot is not a directory: {source}")
        world = find_world_root(source)
        if world is None:
            raise SystemExit(f"no world (level.dat/region) inside {source}")
        snap = dict(snap)
        snap["world"] = world
        snap["source_bytes"] = int(snap.get("source_bytes") or dir_bytes(source))
        prepared.append(snap)
    return prepared


def zstd_jar(explicit: str | None) -> Path:
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    env = os.environ.get("ZSTD")
    if env:
        candidates.append(Path(env))
    cache = Path.home() / ".gradle/caches/modules-2/files-2.1/com.github.luben/zstd-jni"
    if cache.is_dir():
        jars = [p for p in cache.rglob("zstd-jni-*.jar") if "sources" not in p.name]
        candidates.extend(sorted(jars, key=lambda p: natural_key(p.name)))
    for candidate in reversed(candidates):
        if candidate.is_file():
            return candidate
    raise SystemExit("zstd-jni jar not found; pass --zstd /path/to/zstd-jni.jar")


def engine_sources(project: Path) -> list[Path]:
    root = project / "src/main/java/io/github/linkfgfgui/minimalbackup/engine"
    if not root.is_dir():
        raise SystemExit(f"engine sources not found under {root}")
    return sorted(root.rglob("*.java"))


def source_fingerprint(files: list[Path], project: Path) -> str:
    h = hashlib.sha256()
    for path in files:
        h.update(str(path.relative_to(project)).encode())
        h.update(b"\0")
        h.update(path.read_bytes())
    return h.hexdigest()


def compile_all(project: Path, zstd: Path) -> dict:
    sources = engine_sources(project)
    engine_out = OUT / "engine"
    tools_out = OUT / "tools"
    for directory in (engine_out, tools_out):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)
    print(f"[bench] compiling {len(sources)} engine sources from {project}", flush=True)
    subprocess.run(["javac", "--release", "17", "-cp", str(zstd), "-d", str(engine_out),
                    *map(str, sources)], check=True)
    subprocess.run(["javac", "--release", "17", "-cp", f"{zstd}:{engine_out}",
                    "-d", str(tools_out), str(HERE / "tools/DiffBench.java")], check=True)
    return {"project": str(project), "source_count": len(sources),
            "source_sha256": source_fingerprint(sources, project)}


def environment() -> dict:
    cpu = platform.processor() or "unknown"
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    java = subprocess.run(["java", "-version"], capture_output=True, text=True)
    return {
        "os": f"{platform.system()} {platform.release()}",
        "cpu": cpu,
        "cores": os.cpu_count(),
        "memory_gb": round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9, 1)
        if hasattr(os, "sysconf") else None,
        "java": (java.stderr or java.stdout).splitlines()[0] if (java.stderr or java.stdout) else "",
        "python": platform.python_version(),
    }


def run_config(label: str, level: int, long_mode: bool, manifest: Path, heap: str,
               zstd: Path, out_dir: Path, study_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    cp = f"{zstd}:{OUT / 'engine'}:{OUT / 'tools'}"
    cmd = ["java", f"-Xmx{heap}", "-cp", cp, "DiffBench", str(manifest), str(out_dir),
           str(level), str(long_mode).lower()]
    (out_dir / "command.txt").write_text(" ".join(cmd) + "\n", encoding="utf-8")
    print(f"[bench] run {label}: zstd level {level}, long={str(long_mode).lower()}", flush=True)
    started = time.time()
    with (out_dir / "log.txt").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, bufsize=1)
        assert process.stdout is not None
        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            log.write(line)
        code = process.wait()
    elapsed = int((time.time() - started) * 1000)
    if code != 0:
        raise SystemExit(f"run {label} failed with exit code {code}; see {out_dir / 'log.txt'}")
    return {"id": label, "level": level, "long": long_mode,
            "dir": str(out_dir.relative_to(study_dir)), "heap": heap,
            "elapsed_ms": elapsed}


def write_study(name: str, study_dir: Path, snapshots: list[dict], engine: dict,
                env: dict, runs: list[dict], args) -> Path:
    meta = {}
    if args.meta:
        meta = json.loads(Path(args.meta).read_text(encoding="utf-8"))
    study = {
        "schema": 1,
        "name": name,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "dataset": {
            "source": str(Path(args.zip or args.saves or args.manifest).resolve()) if
            (args.zip or args.saves or args.manifest) else "",
            "snapshots": [{"label": s["label"], "source_bytes": s["source_bytes"],
                           "kind": s["kind"],
                           **({"roots": s["roots"]} if "roots" in s else {})}
                          for s in snapshots],
            "total_source_bytes": sum(s["source_bytes"] for s in snapshots),
            **meta,
        },
        "engine": engine,
        "environment": env,
        "runs": runs,
        "argv": sys.argv,
    }
    path = study_dir / "study.json"
    path.write_text(json.dumps(study, indent=2) + "\n", encoding="utf-8")
    return path


def cmd_run(args) -> int:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.name):
        raise SystemExit("--name may only contain letters, digits, dot, dash, underscore")
    study_dir = RESULTS / args.name
    if study_dir.exists() and not args.force:
        raise SystemExit(f"{study_dir} exists; pass --force to replace it")
    levels = [int(v) for v in args.levels.split(",") if v.strip()]
    long_modes = [v.strip().lower() in ("1", "on", "true", "yes")
                  for v in args.long.split(",") if v.strip()]
    if not levels or not long_modes:
        raise SystemExit("empty --levels/--long")
    project = Path(args.project).resolve()
    zstd = zstd_jar(args.zstd)

    snapshots = prepare(collect_snapshots(args))
    for snap in snapshots:
        where = snap.get("world") or snap.get("roots") or ""
        print(f"[bench] snapshot {snap['label']}: {where} "
              f"({snap['source_bytes'] / 1e6:.1f} MB source)", flush=True)

    if study_dir.exists():
        shutil.rmtree(study_dir)
    study_dir.mkdir(parents=True)
    manifest = study_dir / "manifest.tsv"
    if args.raw_manifest:
        shutil.copyfile(args.manifest, manifest)
    else:
        manifest.write_text("# label\tworld\tsource_bytes\n" + "".join(
            f"{s['label']}\t{s['world']}\t{s['source_bytes']}\n" for s in snapshots),
            encoding="utf-8")

    engine = compile_all(project, zstd)
    runs = []
    for level in levels:
        for long_mode in long_modes:
            run_id = f"zstd-l{level}" + ("-long" if long_mode else "")
            runs.append(run_config(run_id, level, long_mode, manifest, args.heap, zstd,
                                   study_dir / run_id, study_dir))
    study = write_study(args.name, study_dir, snapshots, engine, environment(), runs, args)
    print(f"[bench] study: {study}")
    subprocess.run([sys.executable, str(HERE / "tools/report.py"), str(study_dir)], check=True)
    print(f"[bench] report: {study_dir / 'report.html'}")
    return 0


def cmd_report(args) -> int:
    study_dir = Path(args.study).resolve()
    if not (study_dir / "study.json").is_file():
        raise SystemExit(f"no study.json in {study_dir}")
    subprocess.run([sys.executable, str(HERE / "tools/report.py"), str(study_dir)], check=True)
    return 0


def cmd_list(args) -> int:
    if not RESULTS.is_dir():
        print("no studies yet")
        return 0
    for path in sorted(RESULTS.iterdir(), key=lambda p: p.name):
        study = path / "study.json"
        if study.is_file():
            data = json.loads(study.read_text(encoding="utf-8"))
            print(f"{path.name:32s} {data.get('created', ''):20s} "
                  f"{len(data.get('dataset', {}).get('snapshots', []))} snapshots, "
                  f"{len(data.get('runs', []))} configs")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="bench.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="benchmark a series of full saves")
    run.add_argument("--saves", help="directory of snapshot directories/archives")
    run.add_argument("--zip", help="zip containing full-save .tar.gz members (legacy layout)")
    run.add_argument("--manifest", help="explicit label<TAB>path manifest")
    run.add_argument("--raw-manifest", action="store_true",
                     help="manifest is already in engine form (roots, bytes, prepare command)")
    run.add_argument("--meta", help="JSON file merged into dataset metadata")
    run.add_argument("--order", choices=("name", "mtime"), default="name")
    run.add_argument("--project", default=str(DEFAULT_PROJECT), help="engine source project")
    run.add_argument("--levels", default="3", help="comma-separated zstd levels (default 3)")
    run.add_argument("--long", default="off", help="comma-separated long-mode flags (off,on)")
    run.add_argument("--name", default=time.strftime("run-%Y%m%d-%H%M%S"))
    run.add_argument("--heap", default="12g", help="JVM heap for each run (default 12g)")
    run.add_argument("--zstd", help="path to zstd-jni jar")
    run.add_argument("--force", action="store_true", help="replace an existing study")
    run.set_defaults(func=cmd_run)

    report = sub.add_parser("report", help="rebuild the HTML/Markdown report for a study")
    report.add_argument("study")
    report.set_defaults(func=cmd_report)

    listing = sub.add_parser("list", help="list studies under results/")
    listing.set_defaults(func=cmd_list)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
