from collections.abc import Callable

import pytest

from lectern.ingest import html_artifact
from lectern.models import IngestError


def test_sections_notes_and_nested_groups(fixture_bytes: Callable[[str], bytes]) -> None:
    deck = html_artifact.parse(fixture_bytes("artifact.html"), "artifact.html")
    assert deck.title == "Fixture artifact deck"
    assert deck.source == "html"
    assert [s.title for s in deck.slides] == ["First slide", "Vertical one", "Vertical two", "A div slide"]
    assert [s.n for s in deck.slides] == [1, 2, 3, 4]
    first, one, two, last = deck.slides
    assert first.body == "Intro text & more."
    assert first.notes == "Notes for the first slide."
    assert one.notes == ""
    assert two.notes == "Notes from an attribute."
    assert last.persona == "Speak like a pirate."
    assert "window.x" not in last.body


def test_slide_html_keeps_markup_and_styles_but_not_notes(fixture_bytes: Callable[[str], bytes]) -> None:
    deck = html_artifact.parse(fixture_bytes("artifact.html"))
    first = deck.slides[0].html or ""
    assert first.startswith("<style>h2 > em { color: red; }</style><section>")
    assert "Intro text &amp; more." in first
    assert "Notes for the first slide" not in first
    assert "data-notes" not in (deck.slides[2].html or "")
    assert "<br>" in (deck.slides[2].html or "")


def test_no_slides_is_an_error() -> None:
    with pytest.raises(IngestError, match="no <section>"):
        html_artifact.parse(b"<html><body><p>hi</p></body></html>", "x.html")


def test_title_falls_back_to_file_name() -> None:
    deck = html_artifact.parse(b"<section><p>only text</p></section>", "my-talk.html")
    assert deck.title == "my-talk"
    assert deck.slides[0].title == ""
    assert deck.slides[0].body == "only text"
