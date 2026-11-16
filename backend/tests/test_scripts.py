"""The repo hygiene scripts: the size budget and the forbidden-path check."""

import importlib.util
import sys
from pathlib import Path, PurePosixPath
from types import ModuleType

import pytest
from conftest import REPO


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses look their module up here
    spec.loader.exec_module(module)
    return module


def test_forbidden_paths() -> None:
    check = load("check_forbidden_paths")
    assert check.path_problem(PurePosixPath("backend/lectern/api.py")) is None
    assert check.path_problem(PurePosixPath("x/solution/fix.py")) == "solution/ directory"
    assert check.path_problem(PurePosixPath("backend/tests/grader/test_x.py")) == "tests/grader/ directory"
    assert check.path_problem(PurePosixPath("notes/Planted_example.txt")) == "planted* name"
    assert check.path_problem(PurePosixPath("docs/solution.md")) is None


def test_canary_markers(tmp_path: Path) -> None:
    check = load("check_forbidden_paths")
    guid = "-".join(["0" * 8, "1" * 4, "2" * 4, "3" * 4, "4" * 12])
    marked = tmp_path / "a.md"
    marked.write_text(f"# canary GUID {guid}\n")
    banner = tmp_path / "b.md"
    banner.write_text("DATA SHOULD NEVER APPEAR IN TRAINING\nCORPORA.\n")
    clean = tmp_path / "c.md"
    clean.write_text("a guid on its own is fine: " + guid)
    binary = tmp_path / "d.bin"
    binary.write_bytes(b"\xff\xfe\x00")
    assert check.content_problem(marked) == "benchmark canary marker"
    assert check.content_problem(banner) == "benchmark canary marker"
    assert check.content_problem(clean) is None
    assert check.content_problem(binary) is None
    assert check.main() == 0


def test_loc_counting_rules() -> None:
    loc = load("loc_budget")
    source = '"""Doc\nstring."""\n\n# comment\nx = 1\n\n\ndef f():\n    """Doc."""\n    return x\n'
    assert loc.python_lines(source) == {5, 8, 10}
    assert list(loc.python_functions(source)) == [("f", 8, 10)]
    ts = "// note\n/* a\n b */\nexport function F() {\n  return (\n    <p />\n  );\n}\n"
    assert loc.text_lines(ts) == {4, 5, 6, 7, 8}
    assert [(lo, hi) for _, lo, hi in loc.ts_functions(ts)] == [(4, 8)]
    report, problems = loc.check()
    assert problems == [] and len(report) == 3


def test_demo_runs_offline_and_is_safe_to_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The v0.2 demo: an AI client builds the deck and its DNA over MCP, then asks three slides."""
    import asyncio

    for key in ("EXA_API_KEY", "OPENROUTER_API_KEY", "LECTERN_PROVIDER"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("LECTERN_DB", str(tmp_path / "demo.db"))
    monkeypatch.setenv("LECTERN_BLOBS", str(tmp_path / "blobs"))
    demo = load("demo")
    assert asyncio.run(demo.main()) == 0
    out = capsys.readouterr().out
    assert "8 DNA records logged over MCP" in out and "for slide 2 [dna:" in out
    assert "basereliable" not in out and "reliable but narrow" in out  # table cells keep their spacing
    assert out.count("answered (answer;") == 2 and "abstained (abstain; no source holds the answer)" in out
    assert asyncio.run(demo.main()) == 0
    assert "already built; slides refreshed, DNA kept" in capsys.readouterr().out
