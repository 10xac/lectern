from lectern.models import Deck, Slide, TraceStep
from lectern.search import bm25, search_attachments, search_slides, tokenize, top_k
from lectern.stem import stem
from lectern.store import Store


def test_tokenize_drops_stopwords() -> None:
    assert tokenize("What is the Harbour cafe's Q3?") == ["harbour", "cafe", "s", "q3"]


def test_stemmer_matches_morphological_variants() -> None:
    assert stem("growing") == stem("grow")
    assert stem("customers") == stem("customer")
    assert stem("increased") == stem("increase")
    assert stem("sales") == stem("sale")
    assert stem("running") == stem("run")


def test_bm25_matches_via_stemming() -> None:
    docs = ["Sales increased 40% last quarter", "The team hired new staff", "Weather was sunny"]
    assert top_k("increasing sales", docs, 1) == [0]


def test_bm25_prefers_rare_matching_words() -> None:
    docs = ["coffee coffee beans", "coffee harbour", "tea"]
    scores = bm25("harbour coffee", docs)
    assert scores[1] > scores[0] > scores[2] == 0
    assert top_k("harbour coffee", docs, 5) == [1, 0]
    assert bm25("x", []) == []


def test_ties_keep_input_order() -> None:
    assert top_k("same", ["same", "same", "same"], 2) == [0, 1]


def test_store_round_trip_and_scoped_chunks() -> None:
    store = Store()
    a = store.add_deck(Deck(title="A", source="html", slides=[Slide(n=1, title="one")]))
    b = store.add_deck(Deck(title="B", source="pptx", slides=[Slide(n=1, title="uno")]))
    store.add_attachment(a, "a.txt", ["apples are red"])
    store.add_attachment(b, "b.txt", ["apples are green"])
    assert [d.title for d in store.list_decks()] == ["B", "A"]
    assert store.get_deck(999) is None
    assert [c.text for c in search_attachments(store, a, "apples")] == ["apples are red"]
    assert [x.name for x in store.attachments(b)] == ["b.txt"]
    assert store.attachments(b)[0].chunks == 1


def test_traces_round_trip() -> None:
    store = Store()
    trace_id = store.add_trace(
        None, "answer", "slide-1", "done", [TraceStep(index=0, node="gate", outcome="continue")]
    )
    trace = store.get_trace(trace_id)
    assert trace is not None and trace.steps[0].node == "gate"
    assert store.get_trace(trace_id + 1) is None


def test_search_slides() -> None:
    deck = Deck(
        title="d", source="html", slides=[Slide(n=1, title="cats"), Slide(n=2, title="dogs", notes="cats")]
    )
    assert search_slides(deck, "dogs") == [2]
    assert search_slides(deck, "cats", k=1) == [1]


def test_bm25f_title_outweighs_notes() -> None:
    """A term in the title should beat the same term in the notes."""
    deck = Deck(
        title="d",
        source="html",
        slides=[
            Slide(n=1, title="Revenue growth", body="summary", notes="details about team"),
            Slide(n=2, title="Team update", body="summary", notes="details about revenue growth"),
        ],
    )
    # "revenue" in title (slide 1) should outrank "revenue" in notes (slide 2)
    assert search_slides(deck, "revenue", k=1) == [1]
