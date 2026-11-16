"""Shared fixtures: an in-memory store, a fake clock and the three fixture decks."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from lectern import service
from lectern.models import Deck
from lectern.store import Store

FIXTURES = Path(__file__).parent / "fixtures" / "decks"
REPO = Path(__file__).resolve().parents[2]


class FakeClock:
    """Each call is 1 ms after the last, so trace timings are exact."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        self.now += 0.001
        return self.now


@pytest.fixture
def store() -> Store:
    return Store(":memory:")


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def fixture_bytes() -> Callable[[str], bytes]:
    return lambda name: (FIXTURES / name).read_bytes()


def ingest(store: Store, path: Path) -> Deck:
    run = service.run_ingest(store, path.name, path.read_bytes(), clock=FakeClock())
    assert run.state.deck is not None and run.state.deck.id is not None, run.outcome
    return run.state.deck


@pytest.fixture
def html_deck(store: Store) -> Deck:
    return ingest(store, FIXTURES / "artifact.html")


@pytest.fixture
def kettle(store: Store) -> Deck:
    """The pptx seed deck with its CSV attachment."""
    deck = ingest(store, REPO / "decks" / "kettle-quarterly-review.pptx")
    assert deck.id is not None
    csv = REPO / "decks" / "kettle-quarterly-review.data.csv"
    service.attach(store, deck.id, csv.name, csv.read_bytes())
    return deck
