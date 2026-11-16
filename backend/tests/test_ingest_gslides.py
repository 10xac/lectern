from collections.abc import Callable

import pytest
from conftest import REPO

from lectern.ingest import gslides
from lectern.models import IngestError


def test_fixture_export(fixture_bytes: Callable[[str], bytes]) -> None:
    deck = gslides.parse(fixture_bytes("gslides.json"), "gslides.json")
    assert deck.title == "Fixture export"
    assert deck.source == "gslides"
    assert [(s.n, s.title) for s in deck.slides] == [(1, "Opening"), (2, "Middle"), (3, "Table slide")]
    assert [s.notes for s in deck.slides] == ["Notes for slide one.", "", "Notes for slide three."]
    assert deck.slides[2].body.splitlines() == ["Prices below.", "Plan | Price", "Basic | 10", "Pro | 25"]


def test_seed_deck_parses() -> None:
    path = REPO / "decks" / "support-desk-onboarding.json"
    deck = gslides.parse(path.read_bytes(), path.name)
    assert len(deck.slides) == 5
    assert deck.slides[3].notes == ""
    assert "Urgent | 1 hour | 1 day" in deck.slides[2].body


@pytest.mark.parametrize("data", [b"{not json", b'{"title": "x"}', b"[]"])
def test_bad_exports(data: bytes) -> None:
    with pytest.raises(IngestError):
        gslides.parse(data, "bad.json")
