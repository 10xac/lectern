"""BM25 ranking in pure Python, plus the two searches the agents use.

BM25 scores a document higher when it contains the query's words, more so for rare words, and
less so for long documents. Ties keep the input order, so a ranking is deterministic.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence

from lectern.models import Chunk, Deck
from lectern.store import Store

K1 = 1.5
B = 0.75
_WORD = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset(
    "a an and are as at be by do does for from has have how i in is it its of on or our that the"
    " this to was we what when where which who why will with you your".split()
)


def tokenize(text: str) -> list[str]:
    """Lower-case words without stopwords."""
    return [w for w in _WORD.findall(text.lower()) if w not in STOPWORDS]


def bm25(query: str, docs: Sequence[str]) -> list[float]:
    """One BM25 score per document, in the order given."""
    tokens = [tokenize(d) for d in docs]
    if not tokens:
        return []
    avg = sum(len(t) for t in tokens) / len(tokens) or 1.0
    df: Counter[str] = Counter()
    for t in tokens:
        df.update(set(t))
    n = len(tokens)
    scores = []
    for t in tokens:
        tf = Counter(t)
        score = 0.0
        for q in set(tokenize(query)):
            if q not in tf:
                continue
            idf = math.log(1 + (n - df[q] + 0.5) / (df[q] + 0.5))
            score += idf * tf[q] * (K1 + 1) / (tf[q] + K1 * (1 - B + B * len(t) / avg))
        scores.append(score)
    return scores


def top_k(query: str, docs: Sequence[str], k: int) -> list[int]:
    """Indexes of the ``k`` best documents with a positive score, best first (ties: input order)."""
    scores = bm25(query, docs)
    ranked = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    return [i for i in ranked[:k] if scores[i] > 0]


def search_attachments(store: Store, deck_id: int, query: str, k: int = 3) -> list[Chunk]:
    """The ``k`` attachment chunks of this deck that best match ``query``."""
    chunks = store.chunks(deck_id)
    return [chunks[i] for i in top_k(query, [c.text for c in chunks], k)]


def search_slides(deck: Deck, query: str, k: int = 3) -> list[int]:
    """Numbers of the ``k`` slides that best match ``query`` (title, body and notes)."""
    docs = [f"{s.title}\n{s.body}\n{s.notes}" for s in deck.slides]
    return [deck.slides[i].n for i in top_k(query, docs, k)]
