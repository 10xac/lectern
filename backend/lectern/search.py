"""BM25 and BM25F ranking in pure Python, plus the two searches the agents use.

BM25F extends BM25 with per-field weights: a term in the title counts more than the same term
in the notes. ``search_slides`` uses BM25F with title 2×, body 1.5×, notes 1×.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence

from lectern.models import Chunk, Deck
from lectern.stem import stem
from lectern.store import Store

K1, B = 1.5, 0.75
W_TITLE, W_BODY, W_NOTES = 2.0, 1.5, 1.0
_WORD = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset(
    "a an and are as at be by do does for from has have how i in is it its of on or our that the"
    " this to was we what when where which who why will with you your".split()
)


def tokenize(text: str) -> list[str]:
    return [stem(w) for w in _WORD.findall(text.lower()) if w not in STOPWORDS]


def _ranked(scores: Sequence[float], k: int) -> list[int]:
    ranked = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    return [i for i in ranked[:k] if scores[i] > 0]


def bm25(query: str, docs: Sequence[str]) -> list[float]:
    tokens = [tokenize(d) for d in docs]
    if not tokens:
        return []
    avg = sum(len(t) for t in tokens) / len(tokens) or 1.0
    df: Counter[str] = Counter()
    for t in tokens:
        df.update(set(t))
    n, q_terms = len(tokens), set(tokenize(query))
    scores = []
    for t in tokens:
        tf, score = Counter(t), 0.0
        for q in q_terms:
            if q not in tf:
                continue
            idf = math.log(1 + (n - df[q] + 0.5) / (df[q] + 0.5))
            score += idf * tf[q] * (K1 + 1) / (tf[q] + K1 * (1 - B + B * len(t) / avg))
        scores.append(score)
    return scores


def bm25f(query: str, fields: Sequence[Sequence[str]], weights: Sequence[float]) -> list[float]:
    n = len(fields)
    if not n:
        return []
    nf = len(weights)
    ftok = [[tokenize(fields[i][f]) for f in range(nf)] for i in range(n)]
    favg = [sum(len(ftok[i][f]) for i in range(n)) / n or 1.0 for f in range(nf)]
    df: Counter[str] = Counter()
    for i in range(n):
        terms: set[str] = set()
        for f in range(nf):
            terms.update(ftok[i][f])
        df.update(terms)
    q_terms = set(tokenize(query))
    scores: list[float] = []
    for i in range(n):
        score = 0.0
        for q in q_terms:
            wtf = sum(weights[f] * Counter(ftok[i][f]).get(q, 0) / (1 - B + B * len(ftok[i][f]) / favg[f])
                      for f in range(nf))
            if wtf > 0:
                score += math.log(1 + (n - df[q] + 0.5) / (df[q] + 0.5)) * wtf / (K1 + wtf)
        scores.append(score)
    return scores


def top_k(query: str, docs: Sequence[str], k: int) -> list[int]:
    return _ranked(bm25(query, docs), k)


def search_attachments(store: Store, deck_id: int, query: str, k: int = 3) -> list[Chunk]:
    chunks = store.chunks(deck_id)
    return [chunks[i] for i in top_k(query, [c.text for c in chunks], k)]


def search_slides(deck: Deck, query: str, k: int = 3, hybrid: object = None) -> list[int]:
    fields = [[s.title, s.body, s.notes] for s in deck.slides]
    bm25_ranking = [deck.slides[i].n for i in _ranked(bm25f(query, fields, [W_TITLE, W_BODY, W_NOTES]), k * 2)]
    if hybrid is not None:
        try:
            from lectern.embeddings import search_slides_hybrid
            embedder, estore = hybrid
            return search_slides_hybrid(embedder, estore, deck, query, bm25_ranking, k)
        except (ImportError, TypeError, ValueError):
            pass
    return bm25_ranking[:k]
