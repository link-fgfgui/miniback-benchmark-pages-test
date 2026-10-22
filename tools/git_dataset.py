#!/usr/bin/env python3
"""Turn a git repository of full world saves into a benchmark manifest.

Every commit is a complete save. A commit is *effective* when it changes at least one file
the engine actually tracks: any .mca, level.dat, playerdata/*.dat, or data/**/*.dat. Commits
that only touch README files, server logs, session.lock or level.dat_old are skipped, which
is exactly the set of files the engine ignores.

The manifest points at one live directory per repository. Its prepare column materialises
the commit just before DiffBench scans it, so a 4000-commit history needs one world copy on
disk instead of 4000.

    git_dataset.py --git-dir repos/world.git --url https://github.com/x/world \
        --dest work/git/world --manifest results/git-world/manifest.tsv \
        --meta results/git-world/dataset.json
"""
from __future__ import annotations

import argparse
import json
import os
import posixpath
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
MATERIALIZER = HERE / "git_materialize.py"


def git(git_dir: Path, *args: str) -> bytes:
    process = subprocess.run(["git", f"--git-dir={git_dir}", *args],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed:\n"
                         f"{process.stderr.decode('utf-8', 'replace')}")
    return process.stdout


def default_branch(git_dir: Path) -> str:
    process = subprocess.run(["git", f"--git-dir={git_dir}", "symbolic-ref", "--short", "HEAD"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode == 0:
        return process.stdout.decode().strip()
    return "HEAD"


def detect_roots(git_dir: Path) -> list[str]:
    """Every directory that ever contained a level.dat, outermost wins."""
    payload = git(git_dir, "rev-list", "--objects", "--all")
    roots = set()
    for raw in payload.splitlines():
        _, _, path = raw.partition(b" ")
        if not path:
            continue
        text = path.decode("utf-8", "surrogateescape")
        if text == "level.dat" or text.endswith("/level.dat"):
            roots.add(posixpath.dirname(text) or ".")
    if not roots:
        raise SystemExit("no level.dat anywhere in this repository")
    ordered = sorted(roots, key=lambda r: (r.count("/"), len(r), r))
    kept: list[str] = []
    for root in ordered:
        if root == ".":
            return ["."]
        if any(root == k or root.startswith(k + "/") for k in kept):
            continue
        kept.append(root)
    return kept


def is_tracked(local: str) -> bool:
    if local.endswith(".mca"):
        return True
    if local == "level.dat":
        return True
    if local.startswith("playerdata/") and local.endswith(".dat"):
        return True
    if local.endswith(".dat") and "data" in local.split("/")[:-1]:
        return True
    return False


def local_path(path: str, roots: list[str]) -> tuple[str, str] | None:
    best = None
    for root in roots:
        if root == ".":
            local = path
        elif path.startswith(root + "/"):
            local = path[len(root) + 1:]
        else:
            continue
        if not local:
            continue
        if best is None or len(root) > len(best[0]):
            best = (root, local)
    return best


def parse_name_status(payload: bytes) -> list[tuple[str, str]]:
    parts = payload.split(b"\0")
    if parts and parts[-1] == b"":
        parts.pop()
    items = []
    i = 0
    while i + 1 < len(parts):
        status = parts[i].decode("ascii", "replace")[:1]
        path = parts[i + 1].decode("utf-8", "surrogateescape")
        items.append((status, path))
        i += 2
    return items


def changed_paths(git_dir: Path, sha: str) -> list[tuple[str, str]]:
    payload = git(git_dir, "diff-tree", "--root", "--no-commit-id", "--name-status",
                  "-r", "-z", "--no-renames", sha)
    return parse_name_status(payload)


def tree_bytes(git_dir: Path, sha: str, roots: list[str]) -> int:
    pathspec = [] if roots == ["."] else roots
    payload = git(git_dir, "ls-tree", "-r", "-l", "-z", sha, "--", *pathspec)
    total = 0
    for record in payload.split(b"\0"):
        if not record:
            continue
        head, _, _path = record.partition(b"\t")
        fields = head.split()
        if len(fields) >= 4 and fields[1] == b"blob":
            try:
                total += int(fields[3])
            except ValueError:
                pass
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--git-dir", required=True)
    parser.add_argument("--url", default="")
    parser.add_argument("--name", required=True)
    parser.add_argument("--dest", required=True, help="live working directory for the benchmark")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--meta", required=True)
    parser.add_argument("--branch", default="")
    parser.add_argument("--limit", type=int, default=0, help="stop after N effective commits")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    git_dir = Path(args.git_dir).resolve()
    dest = Path(args.dest).resolve()
    manifest = Path(args.manifest).resolve()
    meta_path = Path(args.meta).resolve()
    manifest.parent.mkdir(parents=True, exist_ok=True)
    meta_path.parent.mkdir(parents=True, exist_ok=True)

    branch = args.branch or default_branch(git_dir)
    roots = detect_roots(git_dir)
    log = git(git_dir, "log", "--reverse", "--no-merges", "--format=%H %ct", branch)
    commits = []
    for line in log.decode("ascii", "replace").splitlines():
        if not line.strip():
            continue
        sha, _, epoch = line.partition(" ")
        commits.append((sha, int(epoch)))

    if not args.quiet:
        print(f"[git] {args.name}: {len(commits)} commits on {branch}, roots={roots}",
              flush=True)

    entries = []
    skipped = 0
    previous_effective = None
    changes_dir = manifest.parent / "changes"
    for sha, epoch in commits:
        changes = changed_paths(git_dir, sha)
        effective = []
        for status, path in changes:
            hit = local_path(path, roots)
            if hit and is_tracked(hit[1]):
                effective.append((status, path))
        if not effective:
            skipped += 1
            continue
        index = len(entries) + 1
        stamp = datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y%m%d-%H%M%S")
        label = f"{index:05d}-{stamp}-{sha[:7]}"
        size = tree_bytes(git_dir, sha, roots)
        command = shlex.join([
            sys.executable, str(MATERIALIZER), "--git-dir", str(git_dir), "--sha", sha,
            "--dest", str(dest), "--roots", ";".join(roots), "--quiet",
        ])
        changes_file = None
        if previous_effective is not None:
            changes_dir.mkdir(parents=True, exist_ok=True)
            changes_file = changes_dir / f"{index:05d}.tsv"
            pathspec = [] if roots == ["."] else roots
            payload = git(git_dir, "diff", "--name-status", "-z", "--no-renames",
                          previous_effective, sha, "--", *pathspec)
            lines = []
            for status, path in parse_name_status(payload):
                hit = local_path(path, roots)
                if hit is None:
                    continue
                root, local = hit
                # Keys are relative to the world root for a single root, and namespaced by the
                # root directory when a snapshot combines sibling dimensions.
                key = path if len(roots) > 1 else local
                lines.append(f"{status}\t{key}")
            changes_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        entries.append({"label": label, "sha": sha, "epoch": epoch, "source_bytes": size,
                        "tracked_changes": len(effective), "command": command,
                        "changes": str(changes_file) if changes_file else ""})
        previous_effective = sha
        if not args.quiet and index % 100 == 0:
            print(f"[git] {args.name}: {index} effective commits", flush=True)
        if args.limit and index >= args.limit:
            break

    if not entries:
        raise SystemExit(f"no effective commit in {git_dir}")

    # DiffBench resolves roots against its own working directory, so publish absolute paths
    # inside the live directory; the materialiser keeps using repository-relative roots.
    live_roots = [str(dest) if root == "." else str(dest / root) for root in roots]
    lines = ["# label\tworld roots (; separated)\tsource bytes\tprepare command",
             f"# generated by tools/git_dataset.py from {args.url or git_dir}"]
    for entry in entries:
        lines.append("\t".join([entry["label"], ";".join(live_roots),
                                str(entry["source_bytes"]), entry["command"],
                                entry["changes"]]))
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")

    counts = {}
    for line in git(git_dir, "count-objects", "-v").decode("ascii", "replace").splitlines():
        key, _, value = line.partition(":")
        try:
            counts[key.strip()] = int(value.strip())
        except ValueError:
            pass
    repo_bytes = (counts.get("size-pack", 0) + counts.get("size", 0)) * 1024

    meta = {
        "kind": "git",
        "repo": args.url or str(git_dir),
        "repo_bytes": repo_bytes,
        "repo_bytes_basis": "git count-objects size + size-pack",
        "git_dir": str(git_dir),
        "branch": branch,
        "roots": roots,
        "commits_total": len(commits),
        "commits_effective": len(entries),
        "commits_skipped": skipped,
        "first_commit": entries[0]["sha"],
        "last_commit": entries[-1]["sha"],
        "first_date": datetime.fromtimestamp(entries[0]["epoch"], timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "last_date": datetime.fromtimestamp(entries[-1]["epoch"], timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_basis": "working-tree apparent bytes at each commit",
        "manifest": str(manifest),
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    if not args.quiet:
        print(f"[git] {args.name}: {len(entries)} effective, {skipped} skipped -> {manifest}",
              flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
