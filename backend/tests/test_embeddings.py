"""Embedding-based hybrid search: RRF, cosine, store, and graceful fallback."""

import math

from lectern.embeddings import EmbeddingStore, Embedder, cosine, rrf
from lectern.models import Deck, Slide
from lectern.search import search_slides
from lectern.store import Store


def test_rrf_merges_two_rankings() -> None:
    # doc 0 is first in ranking A, second in B; doc 1 is the reverse
    merged = rrf([[0, 1, 2], [1, 0, 2]], k=60)
    assert merged[0] in (0, 1)  # tie or near-tie; both appear before 2
    assert 2 == merged[-1]


def test_rrf_single_ranking_preserves_order() -> None:
    assert rrf([[3, 1, 4, 5]]) == [3, 1, 4, 5]


def test_cosine_identical_vectors() -> None:
    v = [1 / math.sqrt(3)] * 3
    assert abs(cosine(v, v) - 1.0) < 1e-6


def test_cosine_orthogonal_vectors() -> None:
    assert abs(cosine([1, 0, 0], [0, 1, 0])) < 1e-6


def test_embedding_store_round_trip() -> None:
    store = Store()
    store.add_deck(Deck(title="T", source="html", slides=[Slide(n=1, title="x")]))
    estore = EmbeddingStore(store)
    estore.save(1, 1, "title", [0.1, 0.2, 0.3])
    estore.save(1, 1, "body", [0.4, 0.5, 0.6])
    vecs = estore.vectors(1)
    assert len(vecs) == 2
    assert vecs[0] == (1, "body", [0.4, 0.5, 0.6])
    assert vecs[1] == (1, "title", [0.1, 0.2, 0.3])


def test_embedding_store_delete_deck() -> None:
    store = Store()
    store.add_deck(Deck(title="T", source="html", slides=[Slide(n=1, title="x")]))
    estore = EmbeddingStore(store)
    estore.save(1, 1, "title", [0.1, 0.2])
    estore.delete_deck(1)
    assert estore.vectors(1) == []


def test_search_slides_works_without_hybrid() -> None:
    """search_slides must work when no hybrid tuple is passed (the default)."""
    deck = Deck(title="d", source="html", slides=[Slide(n=1, title="cats"), Slide(n=2, title="dogs")])
    assert search_slides(deck, "dogs") == [2]


def test_search_slides_hybrid_none_fallback() -> None:
    """Passing hybrid=None (explicitly) falls back to BM25F."""
    deck = Deck(title="d", source="html", slides=[Slide(n=1, title="cats"), Slide(n=2, title="dogs")])
    assert search_slides(deck, "dogs", hybrid=None) == [2]


def test_embedder_available_reflects_import() -> None:
    # This test passes regardless of whether sentence-transformers is installed
    result = Embedder.available()
    assert isinstance(result, bool)
