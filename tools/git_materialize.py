#!/usr/bin/env python3
"""Materialise one git commit of a world into a live directory.

Used as the per-snapshot prepare command by DiffBench. The first call (or a call with a
different root set) extracts the whole world; later calls apply only the diff from the
previously materialised commit, so a history with thousands of commits stays cheap.

    git_materialize.py --git-dir repos/world.git --sha <sha> --dest work/git/world \
        --roots "world" --roots "world_nether;world_the_end"

The directory is a cache: it only ever holds one commit, and the benchmark reads it
immediately after this script returns.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

STATE = ".bench-git-state"


def git(git_dir: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    process = subprocess.run(["git", f"--git-dir={git_dir}", *args],
                             input=input_bytes, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    if process.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed:\n"
                         f"{process.stderr.decode('utf-8', 'replace')}")
    return process.stdout


def archive(git_dir: Path, sha: str, dest: Path, paths: list[str]) -> None:
    """Extract the given paths at sha into dest, replacing existing files."""
    if not paths:
        return
    for start in range(0, len(paths), 400):
        chunk = paths[start:start + 400]
        command = ["git", f"--git-dir={git_dir}", "archive", "--format=tar", sha]
        if chunk != ["."]:
            command += ["--", *chunk]
        producer = subprocess.Popen(command, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
        assert producer.stdout is not None
        consumer = subprocess.run(["tar", "-x", "-C", str(dest)], stdin=producer.stdout,
                                  stderr=subprocess.PIPE)
        producer.stdout.close()
        error = producer.stderr.read() if producer.stderr else b""
        code = producer.wait()
        if code != 0 or consumer.returncode != 0:
            raise SystemExit(f"git archive {sha} failed ({code}/{consumer.returncode}):\n"
                             f"{error.decode('utf-8', 'replace')}"
                             f"{consumer.stderr.decode('utf-8', 'replace')}")


def parse_name_status(payload: bytes) -> list[tuple[str, str]]:
    parts = payload.split(b"\0")
    if parts and parts[-1] == b"":
        parts.pop()
    items = []
    i = 0
    while i + 1 < len(parts):
        status = parts[i].decode("ascii", "replace")
        path = parts[i + 1].decode("utf-8", "surrogateescape")
        items.append((status[:1], path))
        i += 2
    return items


def read_state(dest: Path) -> tuple[str, list[str]] | None:
    path = dest / STATE
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return None
    return lines[0].strip(), lines[1:]


def write_state(dest: Path, sha: str, roots: list[str]) -> None:
    tmp = dest / (STATE + ".tmp")
    tmp.write_text("\n".join([sha, *roots]) + "\n", encoding="utf-8")
    os.replace(tmp, dest / STATE)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--git-dir", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--dest", required=True)
    parser.add_argument("--roots", required=True,
                        help="one root, or several separated by ';' ('.' = repo root)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    git_dir = Path(args.git_dir).resolve()
    dest = Path(args.dest).resolve()
    roots = [r.strip() for r in args.roots.split(";") if r.strip()]
    if not roots:
        raise SystemExit("no roots")
    roots = list(dict.fromkeys(roots))

    dest.mkdir(parents=True, exist_ok=True)
    state = read_state(dest)
    if state and state[0] == args.sha and state[1] == roots:
        return 0

    if state is None or state[1] != roots:
        shutil.rmtree(dest, ignore_errors=True)
        dest.mkdir(parents=True, exist_ok=True)
        archive(git_dir, args.sha, dest, roots)
        write_state(dest, args.sha, roots)
        if not args.quiet:
            print(f"[git] full extract {args.sha[:10]} -> {dest}", flush=True)
        return 0

    previous = state[0]
    pathspec = [] if roots == ["."] else roots
    payload = git(git_dir, "diff", "--name-status", "-z", "--no-renames",
                  previous, args.sha, "--", *pathspec)
    changes = parse_name_status(payload)
    added = []
    removed = []
    for status, path in changes:
        if status == "D":
            removed.append(path)
        else:
            added.append(path)
    for path in removed:
        target = dest / path
        if target.is_symlink() or target.is_file():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
    archive(git_dir, args.sha, dest, added)
    write_state(dest, args.sha, roots)
    if not args.quiet:
        print(f"[git] {previous[:10]} -> {args.sha[:10]}: "
              f"{len(added)} written, {len(removed)} removed", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
