"""Fail if the repo holds anything that looks like an answer key or benchmark material.

lectern is a public practice codebase. It must never contain:

* a ``solution/`` directory or a ``tests/grader/`` directory;
* a file or directory whose name starts with ``planted``;
* a benchmark canary line (a "canary GUID" followed by a UUID, or the usual banner that asks
  for benchmark data to be kept out of training sets).

The patterns are built from pieces so this file does not match itself.
"""

from __future__ import annotations

import itertools
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
CANARY = re.compile("canary" + r"\W+" + "guid" + r"\W+" + UUID, re.IGNORECASE)
BANNER = re.compile(r"\s+".join(["never", "appear", "in", "training", "corpora"]), re.IGNORECASE)
SKIP_DIRS = {".git", ".venv", "node_modules", "dist", ".mypy_cache", ".ruff_cache", "__pycache__"}


def repo_files() -> list[PurePosixPath]:
    """Tracked and untracked-but-not-ignored files (or a plain walk outside git)."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return [PurePosixPath(line) for line in out.splitlines() if line]
    except (OSError, subprocess.CalledProcessError):
        return [
            PurePosixPath(p.relative_to(ROOT).as_posix())
            for p in ROOT.rglob("*")
            if p.is_file() and not SKIP_DIRS & set(p.relative_to(ROOT).parts)
        ]


def path_problem(path: PurePosixPath) -> str | None:
    parts = [p.lower() for p in path.parts]
    if "solution" in parts[:-1]:
        return "solution/ directory"
    if any(a == "tests" and b == "grader" for a, b in itertools.pairwise(parts)):
        return "tests/grader/ directory"
    if any(p.startswith("planted") for p in parts):
        return "planted* name"
    return None


def content_problem(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None  # binary files carry no text markers
    if CANARY.search(text) or BANNER.search(text):
        return "benchmark canary marker"
    return None


def main() -> int:
    problems = []
    for rel in repo_files():
        found = path_problem(rel) or (content_problem(ROOT / rel) if (ROOT / rel).is_file() else None)
        if found:
            problems.append(f"{rel}: {found}")
    for problem in problems:
        print(f"check_forbidden_paths: {problem}", file=sys.stderr)
    if not problems:
        print("check_forbidden_paths: ok")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
