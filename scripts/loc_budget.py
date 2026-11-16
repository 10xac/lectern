"""Keep lectern small enough to read in an afternoon.

Counts non-blank, non-comment lines (Python docstrings count as comments) and fails when:

* backend source (backend/lectern) is over 4,600 lines (3,800 in the v0.2 spec; raised for the owner's
  file registry, D1, the production guard, D10, and user accounts, access tokens and model settings
  managed from the web app, D11 and D12);
* frontend source (frontend/src, not tests) is over 1,800 lines (1,600 before D11 and D12);
* tests and fixtures (backend/tests, frontend tests) are over 2,800 lines (the v0.2 spec sets none);
* any counted file is over 300 lines, or any function is over 60 lines.

TypeScript functions are found with a simple bracket-matching heuristic, which is plenty for
code written in this repo's style.
"""

from __future__ import annotations

import ast
import io
import re
import sys
import tokenize
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_FILE = 300
MAX_FUNCTION = 60
SKIP_TOKENS = {
    tokenize.COMMENT,
    tokenize.NL,
    tokenize.NEWLINE,
    tokenize.INDENT,
    tokenize.DEDENT,
    tokenize.ENCODING,
    tokenize.ENDMARKER,
}
TS_FUNCTION = re.compile(r"\bfunction\b|=>\s*[{(]\s*$")


@dataclass(frozen=True)
class Group:
    name: str
    budget: int
    files: list[Path]


def is_test(path: Path) -> bool:
    return ".test." in path.name or "test" in path.relative_to(ROOT / "frontend/src").parts[:-1]


def groups() -> list[Group]:
    fe = [p for ext in ("ts", "tsx", "css") for p in (ROOT / "frontend/src").rglob(f"*.{ext}")]
    tests = [p for ext in ("py", "html", "json") for p in (ROOT / "backend/tests").rglob(f"*.{ext}")]
    return [
        Group("backend", 4600, sorted((ROOT / "backend/lectern").rglob("*.py"))),
        Group("frontend", 1800, sorted(p for p in fe if not is_test(p))),
        Group("tests", 2800, sorted(tests + [p for p in fe if is_test(p)])),
    ]


def python_lines(source: str) -> set[int]:
    """Line numbers that hold code (not blank, not a comment, not a docstring)."""
    docstrings: set[int] = set()
    for node in ast.walk(ast.parse(source)):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr):
            value = body[0].value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                docstrings.update(range(value.lineno, (value.end_lineno or value.lineno) + 1))
    lines: set[int] = set()
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type not in SKIP_TOKENS:
            lines.update(range(tok.start[0], tok.end[0] + 1))
    return lines - docstrings


def python_functions(source: str) -> Iterable[tuple[str, int, int]]:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield node.name, node.lineno, node.end_lineno or node.lineno


def text_lines(source: str) -> set[int]:
    """Code lines of TS/CSS/HTML/JSON: blank lines and ``//`` or ``/* */`` comments are skipped."""
    lines, in_block = set(), False
    for no, raw in enumerate(source.splitlines(), start=1):
        line = raw.strip()
        if in_block:
            in_block = "*/" not in line
            continue
        if line.startswith("/*"):
            in_block = "*/" not in line
            continue
        if line and not line.startswith("//"):
            lines.add(no)
    return lines


def ts_functions(source: str) -> Iterable[tuple[str, int, int]]:
    rows = source.splitlines()
    for start, line in enumerate(rows):
        if not TS_FUNCTION.search(line):
            continue
        depth, opened = 0, False
        for end in range(start, len(rows)):
            for ch in rows[end]:
                if ch in "{([":
                    depth, opened = depth + 1, True
                elif ch in "})]":
                    depth -= 1
            if opened and depth <= 0:
                break
        yield line.strip()[:40], start + 1, end + 1


def check() -> tuple[list[str], list[str]]:
    report, problems = [], []
    for group in groups():
        total = 0
        for path in group.files:
            source = path.read_text(encoding="utf-8")
            is_py = path.suffix == ".py"
            counted = python_lines(source) if is_py else text_lines(source)
            total += len(counted)
            rel = path.relative_to(ROOT)
            if len(counted) > MAX_FILE:
                problems.append(f"{rel}: {len(counted)} lines (max {MAX_FILE})")
            if path.suffix in (".py", ".ts", ".tsx"):
                for name, lo, hi in (python_functions if is_py else ts_functions)(source):
                    size = len([n for n in counted if lo <= n <= hi])
                    if size > MAX_FUNCTION:
                        problems.append(f"{rel}:{lo} {name}: {size} lines (max {MAX_FUNCTION})")
        status = "ok" if total <= group.budget else "OVER"
        report.append(f"{group.name:<9} {total:>5} / {group.budget:<5} {len(group.files):>3} files  {status}")
        if total > group.budget:
            problems.append(f"{group.name}: {total} lines (budget {group.budget})")
    return report, problems


def main() -> int:
    report, problems = check()
    print("\n".join(report))
    for problem in problems:
        print(f"loc_budget: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
