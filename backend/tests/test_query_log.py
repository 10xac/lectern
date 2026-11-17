"""Query logging: every answered question is recorded with its retrieval signals."""

from lectern import service
from lectern.models import Deck, Slide
from lectern.providers.fake import FakeProvider
from lectern.query_log import QueryLog
from lectern.store import Store
from tests.conftest import FakeClock


def test_ask_logs_query() -> None:
    store = Store()
    deck = Deck(title="T", source="html", slides=[Slide(n=1, title="cats", body="cats are great")])
    deck_id = store.add_deck(deck)
    deck = store.get_deck(deck_id)
    assert deck is not None
    service.ask(store, FakeProvider(), deck, 1, "tell me about cats", clock=FakeClock())
    qlog = QueryLog(store)
    entries = qlog.entries(deck_id)
    assert len(entries) == 1
    e = entries[0]
    assert e.deck_id == deck_id
    assert e.slide == 1
    assert e.question == "tell me about cats"
    assert e.agent == "slide-1"
    assert e.outcome == "done"
    assert len(e.block_ids) > 0
    assert len(e.bm25_scores) > 0
    assert e.trace_id is not None


def test_query_log_filters_by_deck() -> None:
    store = Store()
    d1 = store.add_deck(Deck(title="A", source="html", slides=[Slide(n=1, title="x", body="hello")]))
    d2 = store.add_deck(Deck(title="B", source="html", slides=[Slide(n=1, title="y", body="world")]))
    for did in (d1, d2):
        deck = store.get_deck(did)
        assert deck is not None
        service.ask(store, FakeProvider(), deck, 1, "test", clock=FakeClock())
    qlog = QueryLog(store)
    assert len(qlog.entries()) == 2
    assert len(qlog.entries(d1)) == 1
    assert qlog.entries(d1)[0].deck_id == d1


def test_query_log_deleted_with_deck() -> None:
    store = Store()
    deck_id = store.add_deck(Deck(title="T", source="html", slides=[Slide(n=1, title="x", body="y")]))
    deck = store.get_deck(deck_id)
    assert deck is not None
    service.ask(store, FakeProvider(), deck, 1, "q", clock=FakeClock())
    qlog = QueryLog(store)
    assert len(qlog.entries(deck_id)) == 1
    store.delete_deck(deck_id)
    assert len(qlog.entries(deck_id)) == 0
