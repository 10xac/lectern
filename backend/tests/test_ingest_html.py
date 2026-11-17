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
    assert first.startswith("<section>") and "<style>h2 > em { color: red; }</style>" in (deck.shell or "")
    assert "Intro text &amp; more." in first
    assert "Notes for the first slide" not in first
    assert "data-notes" not in (deck.slides[2].html or "")
    assert "<br>" in (deck.slides[2].html or "")


REVEAL = b"""<!doctype html><html lang="en"><head><title>Talk</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reveal.css">
<style>.reveal h1 { color: teal }</style></head>
<body class="dark"><div class="reveal"><div class="slides">
<section><h1>One</h1></section>
<section><section><h1>Two</h1></section><section><h1>Three</h1></section></section>
</div></div>
<script src="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reveal.js"></script>
<script>Reveal.initialize({hash: true});</script></body></html>"""


def test_framework_decks_keep_their_document_around_each_slide() -> None:
    deck = html_artifact.parse(REVEAL, "talk.html")
    assert [s.title for s in deck.slides] == ["One", "Two", "Three"]
    shell = deck.shell or ""
    head, _, tail = shell.partition(html_artifact.SLIDE_MARK)
    assert 'href="https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reveal.css"' in head
    assert '<html lang="en">' in head and '<body class="dark">' in head
    assert head.endswith('<div class="reveal"><div class="slides">')  # the wrappers its CSS expects
    assert tail.startswith("</div></div>") and "Reveal.initialize" in tail  # scripts run after the slide
    assert "<section>" not in shell  # but no slide of its own


def test_no_slides_is_an_error() -> None:
    with pytest.raises(IngestError, match="no <section>"):
        html_artifact.parse(b"<html><body><p>hi</p></body></html>", "x.html")


def test_title_falls_back_to_file_name() -> None:
    deck = html_artifact.parse(b"<section><p>only text</p></section>", "my-talk.html")
    assert deck.title == "my-talk"
    assert deck.slides[0].title == ""
    assert deck.slides[0].body == "only text"
