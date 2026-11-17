"""Answer cache: LRU, deck-version-aware, bounded."""

from lectern.cache import AnswerCache, deck_hash
from lectern.models import Answer, Deck, Slide


def _deck(title: str = "T", slides: int = 2) -> Deck:
    return Deck(id=1, title=title, source="html", slides=[Slide(n=i + 1, title=f"s{i}") for i in range(slides)])


def _answer(text: str = "yes") -> Answer:
    return Answer(answer=text, agent="slide-1")


def test_cache_hit() -> None:
    cache = AnswerCache()
    deck = _deck()
    cache.put(deck, 1, "hello?", _answer("world"))
    assert cache.get(deck, 1, "hello?") is not None
    assert cache.get(deck, 1, "hello?").answer == "world"


def test_cache_miss_different_question() -> None:
    cache = AnswerCache()
    deck = _deck()
    cache.put(deck, 1, "hello?", _answer())
    assert cache.get(deck, 1, "goodbye?") is None


def test_cache_miss_after_deck_change() -> None:
    cache = AnswerCache()
    deck = _deck()
    cache.put(deck, 1, "hello?", _answer())
    changed = _deck(slides=3)  # different slide count → different hash
    assert cache.get(changed, 1, "hello?") is None


def test_cache_case_insensitive() -> None:
    cache = AnswerCache()
    deck = _deck()
    cache.put(deck, 1, "Hello?", _answer())
    assert cache.get(deck, 1, "hello?") is not None


def test_cache_bounded() -> None:
    cache = AnswerCache(max_size=2)
    deck = _deck()
    cache.put(deck, 1, "q1", _answer("a1"))
    cache.put(deck, 1, "q2", _answer("a2"))
    cache.put(deck, 1, "q3", _answer("a3"))
    assert cache.size == 2
    assert cache.get(deck, 1, "q1") is None  # evicted
    assert cache.get(deck, 1, "q3") is not None


def test_invalidate_deck() -> None:
    cache = AnswerCache()
    deck = _deck()
    cache.put(deck, 1, "q1", _answer())
    cache.put(deck, 2, "q2", _answer())
    removed = cache.invalidate(1)
    assert removed == 2
    assert cache.size == 0


def test_deck_hash_changes_with_content() -> None:
    d1 = _deck()
    d2 = _deck(slides=3)
    d3 = _deck(title="Other")
    assert deck_hash(d1) != deck_hash(d2)
    assert deck_hash(d1) != deck_hash(d3)
