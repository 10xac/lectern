"""A slide agent answers from its own context only, cites assembled blocks, and is deterministic."""

from collections.abc import Sequence

from lectern.graph.nodes.cite import UNSUPPORTED
from lectern.graph.state import Block
from lectern.models import Deck
from lectern.providers.fake import FakeProvider
from lectern.service import ask
from lectern.store import Store


def block_ids(store: Store, trace_id: int | None) -> list[str]:
    trace = store.get_trace(trace_id or 0)
    assert trace is not None
    return next(s.block_ids for s in trace.steps if s.node == "assemble")


def test_answers_from_notes_with_citations(store: Store, kettle: Deck) -> None:
    answer = ask(store, FakeProvider(), kettle, 2, "Why did the harbour cafe grow?")
    assert answer.agent == "slide-2"
    assert answer.outcome == "done"
    assert "ferry timetable" in answer.answer
    assert "[slide:2:notes]" in answer.answer
    assembled = block_ids(store, answer.trace_id)
    assert {c.block_id for c in answer.citations} <= set(assembled)
    assert answer.citations[0].slide == 2


def test_context_is_slide_notes_neighbours_attachments_outline(store: Store, kettle: Deck) -> None:
    answer = ask(store, FakeProvider(), kettle, 2, "How many cups did the harbour sell?")
    ids = block_ids(store, answer.trace_id)
    assert ids[:3] == ["slide:2:title", "slide:2:body", "slide:2:notes"]
    assert ids[3].startswith("att:")
    assert "slide:1:title" in ids and "slide:3:body" in ids
    assert ids[-1] == "deck:outline"
    assert not any(i.startswith("slide:4:") or i.startswith("slide:5:") for i in ids)
    assert any(c.attachment is not None for c in answer.citations)


def test_attachments_of_other_decks_are_never_used(store: Store, kettle: Deck, html_deck: Deck) -> None:
    answer = ask(store, FakeProvider(), html_deck, 1, "How many cups did the harbour sell?")
    assert not any(i.startswith("att:") for i in block_ids(store, answer.trace_id))


def test_fake_provider_is_byte_identical(store: Store, kettle: Deck) -> None:
    first = ask(store, FakeProvider(), kettle, 3, "What did the weekly batch change?")
    second = ask(store, FakeProvider(), kettle, 3, "What did the weekly batch change?")
    assert first.answer.encode("utf-8") == second.answer.encode("utf-8")
    assert first.answer == (
        "Online shipping moved to a weekly batch. [slide:3:body]"
        " 2026-W27, Online, 0, 61, weekly batch shipping starts [att:1:0]"
        " The weekly batch cut shipping costs by a fifth but slowed delivery by two days. [slide:3:notes]"
    )
    assert first.trace_id != second.trace_id


def test_slide_without_notes_has_no_notes_block(store: Store, kettle: Deck) -> None:
    answer = ask(store, FakeProvider(), kettle, 4, "What did customers say?")
    assert "slide:4:notes" not in block_ids(store, answer.trace_id)


def test_gate_refuses_empty_and_long_questions(store: Store, kettle: Deck) -> None:
    empty = ask(store, FakeProvider(), kettle, 1, "   ")
    assert empty.outcome == "refused:empty" and empty.citations == []
    long = ask(store, FakeProvider(), kettle, 1, "x" * 1001)
    assert long.outcome == "refused:too_long"
    trace = store.get_trace(long.trace_id or 0)
    assert trace is not None and [s.node for s in trace.steps] == ["gate", "persist"]


class Inventor:
    """Cites a block that was never in context."""

    name = "inventor"

    def __init__(self) -> None:
        self.systems: list[str] = []

    def complete(self, system: str, blocks: Sequence[Block], question: str) -> str:
        self.systems.append(system)
        return "Made up. [slide:99:notes]"


def test_unverifiable_citations_revise_twice_then_give_up(store: Store, kettle: Deck) -> None:
    provider = Inventor()
    answer = ask(store, provider, kettle, 1, "Explain this slide")
    assert answer.answer == UNSUPPORTED
    assert answer.citations == []
    assert answer.outcome == "unsupported"
    assert len(provider.systems) == 3
    assert "Cite only from these block ids: slide:1:title" in provider.systems[1]
    trace = store.get_trace(answer.trace_id or 0)
    assert trace is not None
    nodes = [s.node for s in trace.steps]
    assert nodes == [
        "gate",
        "route",
        "assemble",
        "answer",
        "cite",
        "answer",
        "cite",
        "answer",
        "cite",
        "persist",
    ]


class HalfRight:
    name = "half"

    def complete(self, system: str, blocks: Sequence[Block], question: str) -> str:
        return f"True. [{blocks[0].id}] Invented. [att:999:0]"


def test_invalid_markers_are_dropped(store: Store, kettle: Deck) -> None:
    answer = ask(store, HalfRight(), kettle, 1, "Explain this slide")
    assert answer.answer == "True. [slide:1:title] Invented."
    assert [c.block_id for c in answer.citations] == ["slide:1:title"]


def test_history_reaches_the_provider(store: Store, kettle: Deck) -> None:
    from lectern.models import Turn

    provider = Inventor()
    ask(
        store,
        provider,
        kettle,
        1,
        "And this?",
        [Turn(role="user", text="Hi"), Turn(role="agent", text="Hello")],
    )
    assert "Earlier in this chat:\nuser: Hi\nagent: Hello" in provider.systems[0]
