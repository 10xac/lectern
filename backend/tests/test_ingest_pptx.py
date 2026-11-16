import subprocess
import sys
from collections.abc import Callable

import pytest
from conftest import FIXTURES, REPO

from lectern.ingest import pptx
from lectern.models import IngestError


def test_sample_deck_titles_body_and_notes() -> None:
    deck = pptx.load_deck(FIXTURES / "sample.pptx")
    assert deck.title == "Sample deck"
    assert deck.source == "pptx"
    assert [s.title for s in deck.slides] == ["Welcome", "Numbers", "No notes here", "A picture"]
    assert [s.notes for s in deck.slides] == [
        "Say hello first.",
        "March was the launch month.",
        "",
        "Point at the March bar.",
    ]


def test_reading_order_tables_and_alt_text(fixture_bytes: Callable[[str], bytes]) -> None:
    deck = pptx.parse(fixture_bytes("sample.pptx"), "sample.pptx")
    numbers = deck.slides[1].body.splitlines()
    assert numbers == [
        "Visitors grew in March.",
        "Month | Visitors",
        "February | 120",
        "March | 180",
        "Bottom box, read second.",
    ]
    assert "[image: Bar chart of visitors per month]" in deck.slides[3].body


def test_broken_file_is_an_ingest_error() -> None:
    with pytest.raises(IngestError, match=r"not a readable \.pptx"):
        pptx.parse(b"PK\x03\x04 not really a zip", "broken.pptx")


def test_checked_in_pptx_files_are_reproducible() -> None:
    script = REPO / "scripts" / "make_sample_pptx.py"
    result = subprocess.run([sys.executable, str(script), "--check"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
