"""detect, attachment chunking and the ingest template end to end."""

from collections.abc import Callable

import pytest
from conftest import FakeClock

from lectern import service
from lectern.ingest import attachments
from lectern.ingest.detect import detect
from lectern.models import IngestError
from lectern.store import Store


@pytest.mark.parametrize(
    ("name", "kind"), [("artifact.html", "html"), ("sample.pptx", "pptx"), ("gslides.json", "gslides")]
)
def test_detect_fixtures(name: str, kind: str, fixture_bytes: Callable[[str], bytes]) -> None:
    assert detect(name, fixture_bytes(name)) == kind


@pytest.mark.parametrize(
    ("name", "data", "message"),
    [
        ("a.zip", b"PK\x03\x04" + b"\x00" * 10, "not a .pptx"),
        ("a.json", b"{oops", "not valid JSON"),
        ("a.json", b'{"pages": []}', "without a 'slides' list"),
        ("a.bin", b"\x00\x01", "unknown deck format"),
    ],
)
def test_detect_refuses(name: str, data: bytes, message: str) -> None:
    with pytest.raises(IngestError, match=message):
        detect(name, data)


@pytest.mark.parametrize("name", ["artifact.html", "sample.pptx", "gslides.json"])
def test_ingest_template_saves_every_source(
    store: Store, name: str, fixture_bytes: Callable[[str], bytes]
) -> None:
    run = service.run_ingest(store, name, fixture_bytes(name), clock=FakeClock())
    assert run.path == ("detect", "parse", "normalise", "index", "persist")
    assert run.outcome == "done"
    deck = store.get_deck(run.state.deck_id or 0)
    assert deck is not None and deck.slides
    assert deck.outline.splitlines()[0].startswith("1. ")
    trace = store.get_trace(run.state.trace_id or 0)
    assert trace is not None and trace.deck_id == deck.id
    assert [s.ms for s in trace.steps[:-1]] == [1.0, 1.0, 1.0, 1.0]


def test_ingest_refusal_saves_no_deck(store: Store) -> None:
    run = service.run_ingest(store, "x.bin", b"\x00\x01")
    assert run.outcome.startswith("refused: x.bin: unknown deck format")
    assert run.path == ("detect", "persist")
    assert store.list_decks() == []


def test_too_many_slides(store: Store) -> None:
    html = "".join(f"<section><h2>S{i}</h2></section>" for i in range(201)).encode()
    run = service.run_ingest(store, "big.html", html)
    assert run.outcome == "refused: more than 200 slides"


def test_untitled_slide_outline_uses_first_line(store: Store) -> None:
    run = service.run_ingest(
        store, "t.html", b"<section><p>first line</p><p>second</p></section><section></section>"
    )
    assert run.state.deck is not None
    assert run.state.deck.outline == "1. first line\n2. (untitled)"


def test_chunking() -> None:
    md = b"# One\nalpha beta\n## Two\ngamma\n"
    assert attachments.chunk("n.md", md) == ["# One alpha beta", "## Two gamma"]
    rows = "h1,h2\n" + "".join(f"{i},x\n" for i in range(45))
    chunks = attachments.chunk("d.csv", rows.encode())
    assert len(chunks) == 3 and all(c.startswith("h1, h2\n") for c in chunks)
    words = " ".join(f"w{i}" for i in range(450)).encode()
    assert [len(c.split()) for c in attachments.chunk("t.txt", words)] == [200, 200, 50]
    assert attachments.chunk("e.csv", b"") == []
    with pytest.raises(IngestError, match="attachments must be one of"):
        attachments.chunk("x.pdf", b"%PDF")
