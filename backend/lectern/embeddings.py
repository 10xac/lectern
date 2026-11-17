"""Optional embedding-based search using sentence-transformers (``pip install lectern[embeddings]``).

Embeds slide text at ingest, stores vectors as JSON in SQLite, ranks by cosine at query time.
If sentence-transformers is absent, ``Embedder.available()`` is ``False`` and Lectern falls back to BM25.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from lectern.store import Store

DEFAULT_MODEL = "all-MiniLM-L6-v2"
SCHEMA = """
CREATE TABLE IF NOT EXISTS embeddings (
  deck_id INTEGER NOT NULL, slide_n INTEGER NOT NULL,
  field TEXT NOT NULL, vec TEXT NOT NULL,
  PRIMARY KEY (deck_id, slide_n, field));
"""


def _try_import() -> Any:
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer
    except ImportError:
        return None


class Embedder:
    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self._model_name, self._model = model_name, None

    @staticmethod
    def available() -> bool:
        return _try_import() is not None

    def _load(self) -> Any:
        if self._model is None:
            cls = _try_import()
            if cls is None:
                raise ImportError("pip install lectern[embeddings]")
            self._model = cls(self._model_name)
        return self._model

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        return [v.tolist() for v in self._load().encode(list(texts), normalize_embeddings=True)]

    def encode_one(self, text: str) -> list[float]:
        return self.encode([text])[0]


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def rrf(rankings: Sequence[Sequence[int]], k: int = 60) -> list[int]:
    """Reciprocal Rank Fusion (Cormack et al., 2009): merge ranked lists."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, doc_idx in enumerate(ranking):
            scores[doc_idx] = scores.get(doc_idx, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda i: (-scores[i], i))


class EmbeddingStore:
    def __init__(self, store: Store) -> None:
        self._store = store
        with store.tx() as db:
            db.executescript(SCHEMA)

    def save(self, deck_id: int, slide_n: int, field: str, vec: list[float]) -> None:
        with self._store.tx() as db:
            db.execute(
                "INSERT OR REPLACE INTO embeddings (deck_id, slide_n, field, vec) VALUES (?, ?, ?, ?)",
                (deck_id, slide_n, field, json.dumps(vec)),
            )

    def vectors(self, deck_id: int) -> list[tuple[int, str, list[float]]]:
        with self._store.tx() as db:
            rows = db.execute(
                "SELECT slide_n, field, vec FROM embeddings WHERE deck_id = ? ORDER BY slide_n, field",
                (deck_id,),
            ).fetchall()
        return [(r["slide_n"], r["field"], json.loads(r["vec"])) for r in rows]

    def delete_deck(self, deck_id: int) -> None:
        with self._store.tx() as db:
            db.execute("DELETE FROM embeddings WHERE deck_id = ?", (deck_id,))


def embed_deck(embedder: Embedder, estore: EmbeddingStore, deck_id: int, slides: Sequence[Any]) -> int:
    count = 0
    for slide in slides:
        for field, text in [("title", slide.title), ("body", slide.body), ("notes", slide.notes)]:
            if text.strip():
                estore.save(deck_id, slide.n, field, embedder.encode_one(text))
                count += 1
    return count


def search_slides_hybrid(
    embedder: Embedder, estore: EmbeddingStore, deck: Any, query: str,
    bm25_ranking: list[int], k: int = 3,
) -> list[int]:
    q_vec = embedder.encode_one(query)
    vectors = estore.vectors(deck.id)
    if not vectors:
        return bm25_ranking[:k]
    slide_scores: dict[int, float] = {}
    for slide_n, field, vec in vectors:
        slide_scores[slide_n] = max(slide_scores.get(slide_n, -1.0), cosine(q_vec, vec))
    emb_ranking = sorted(slide_scores, key=lambda n: (-slide_scores[n], n))
    return rrf([bm25_ranking, emb_ranking])[:k]
