"""In-memory LRU answer cache: same question on same deck version = cached answer."""

from __future__ import annotations

import hashlib
from collections import OrderedDict

from lectern.models import Answer, Deck


def deck_hash(deck: Deck) -> str:
    parts = [deck.title, str(len(deck.slides)), deck.outline]
    for s in deck.slides:
        parts.extend((s.title, s.body, s.notes))
    return hashlib.md5("|".join(parts).encode(), usedforsecurity=False).hexdigest()[:12]


class AnswerCache:
    def __init__(self, max_size: int = 512) -> None:
        self._max = max_size
        self._store: OrderedDict[tuple[int, int | None, str, str], Answer] = OrderedDict()

    def get(self, deck: Deck, slide: int | None, question: str) -> Answer | None:
        key = (deck.id or 0, slide, question.strip().lower(), deck_hash(deck))
        if key in self._store:
            self._store.move_to_end(key)
            return self._store[key]
        return None

    def put(self, deck: Deck, slide: int | None, question: str, answer: Answer) -> None:
        key = (deck.id or 0, slide, question.strip().lower(), deck_hash(deck))
        self._store[key] = answer
        self._store.move_to_end(key)
        while len(self._store) > self._max:
            self._store.popitem(last=False)

    def invalidate(self, deck_id: int) -> int:
        to_remove = [k for k in self._store if k[0] == deck_id]
        for k in to_remove:
            del self._store[k]
        return len(to_remove)

    @property
    def size(self) -> int:
        return len(self._store)
