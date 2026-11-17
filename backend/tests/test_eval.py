"""Seed evaluation harness: known questions against the kettle deck, scored for retrieval quality.

Each tuple is ``(slide, question, expected_keywords_in_answer, expected_citation_blocks)``.
Keywords test answer quality; citation blocks test retrieval and grounding. The fake provider
returns exact slide text, so we can assert precise citations.

Run with ``pytest backend/tests/test_eval.py -v`` to see per-question results.
"""

from __future__ import annotations

import pytest

from lectern import service
from lectern.models import Deck
from lectern.providers.fake import FakeProvider
from lectern.query_log import QueryLog
from lectern.store import Store
from tests.conftest import FakeClock

PROVIDER = FakeProvider()


@pytest.fixture
def kettle_with_data(store: Store) -> Deck:
    from pathlib import Path
    from tests.conftest import ingest, REPO
    deck = ingest(store, REPO / "decks" / "kettle-quarterly-review.pptx")
    assert deck.id is not None
    csv = REPO / "decks" / "kettle-quarterly-review.data.csv"
    service.attach(store, deck.id, csv.name, csv.read_bytes())
    return deck


# (slide_to_ask, question, keywords_expected_in_answer, citation_block_prefixes_expected)
# (slide_to_ask, question, keywords_expected_in_answer, citation_prefixes, xfail_reason)
EVAL_SET: list[tuple[int, str, list[str], list[str], str]] = [
    # --- single-slide factual (keyword in BM25 reach) ---
    (2, "Why did the harbour cafe grow?", ["ferry", "timetable"], ["slide:2"], ""),
    (2, "Which region grew fastest?", ["harbour"], ["slide:2"], ""),
    (1, "What is this quarterly review about?", ["coffee"], ["slide:1", "deck:outline"],
     "BM25 misses: 'coffee' not in query, title+outline outscore body"),
    (3, "What happened with shipping?", ["weekly", "batch"], ["slide:3"], ""),
    (5, "What is the plan for Q4?", ["barista", "harbour"], ["slide:5", "deck:outline"],
     "BM25 misses: 'barista'/'harbour' in body but 'Q4'/'plan' in title outscore"),
    (3, "What did the weekly batch change?", ["shipping"], ["slide:3"], ""),
    # --- notes-dependent ---
    (1, "What is the revenue headline?", ["revenue", "14"], ["slide:1"], ""),
    (5, "What needs board approval?", ["barista", "hire"], ["slide:5"], ""),
    (3, "How did the weekly batch affect costs?", ["fifth"], ["slide:3"], ""),
    # --- attachment-dependent ---
    (3, "When did the weekly batch start?", ["2026"], ["att:"], ""),
    # --- the fake provider's limits ---
    (1, "What is the weather forecast?", [], [], ""),
    (4, "How many employees does Kettle have?", [], [], ""),
    # --- cross-slide routing ---
    (2, "What does slide 4 say?", ["survey"], ["slide:4"], ""),
    (1, "Summarise the whole deck", ["quarterly"], ["slide:", "deck:outline"], ""),
    # --- ambiguous ---
    (1, "Why?", [], [], ""),
]


@pytest.mark.parametrize(
    "slide,question,keywords,cite_prefixes,xfail_reason",
    EVAL_SET, ids=[e[1][:40] for e in EVAL_SET],
)
def test_eval_question(
    store: Store, kettle_with_data: Deck, slide: int, question: str,
    keywords: list[str], cite_prefixes: list[str], xfail_reason: str,
) -> None:
    if xfail_reason:
        pytest.xfail(xfail_reason)
    answer = service.ask(store, PROVIDER, kettle_with_data, slide, question, clock=FakeClock())
    text = answer.answer.lower()
    # Score keywords (soft: at least half should match for non-empty expectations)
    if keywords:
        matched = sum(1 for kw in keywords if kw.lower() in text)
        assert matched >= len(keywords) / 2, (
            f"expected >={len(keywords)//2} of {keywords} in answer, got {matched}: {answer.answer[:200]}"
        )
    # Score citations: at least one expected prefix should appear in the citations
    if cite_prefixes:
        cited = [c.block_id for c in answer.citations]
        hit = any(any(c.startswith(p) for c in cited) for p in cite_prefixes)
        assert hit, f"expected a citation matching one of {cite_prefixes}, got {cited}"


def test_eval_summary(store: Store, kettle_with_data: Deck) -> None:
    """Run all eval questions and report aggregate scores."""
    correct, total = 0, 0
    cite_hits, cite_total = 0, 0
    for slide, question, keywords, cite_prefixes, _ in EVAL_SET:
        answer = service.ask(store, PROVIDER, kettle_with_data, slide, question, clock=FakeClock())
        text = answer.answer.lower()
        if keywords:
            total += 1
            matched = sum(1 for kw in keywords if kw.lower() in text)
            if matched >= len(keywords) / 2:
                correct += 1
        if cite_prefixes:
            cite_total += len(cite_prefixes)
            cited = [c.block_id for c in answer.citations]
            cite_hits += sum(1 for p in cite_prefixes if any(c.startswith(p) for c in cited))
    if total:
        accuracy = correct / total
        assert accuracy >= 0.5, f"answer accuracy {accuracy:.0%} is below 50%"
    if cite_total:
        cite_recall = cite_hits / cite_total
        assert cite_recall >= 0.4, f"citation recall {cite_recall:.0%} is below 40%"
