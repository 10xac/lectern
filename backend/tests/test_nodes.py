"""Nodes on their own, with hand-built state."""

from lectern.graph.nodes.answer import answer
from lectern.graph.nodes.assemble import assemble, fit
from lectern.graph.nodes.persist import persist
from lectern.graph.state import Block, GraphState, Ports, Route
from lectern.models import Deck, Slide


def deck() -> Deck:
    slides = [Slide(n=i, title=f"T{i}", body=f"body {i}", notes=f"notes {i}") for i in (1, 2, 3)]
    return Deck(id=1, title="d", source="html", outline="1. T1\n2. T2\n3. T3", slides=slides)


def test_fit_keeps_order_and_skips_what_does_not_fit() -> None:
    groups = [[Block("a", "x" * 5)], [Block("b", "y" * 10), Block("c", "z" * 3)]]
    assert [b.id for b in fit(groups, 9)] == ["a", "c"]


def test_budget_keeps_current_slide_first() -> None:
    state = GraphState(template="answer", deck=deck(), slide=2, question="q", budget=len("T2body 2notes 2"))
    ids = [b.id for b in assemble(state, Ports()).delta["blocks"]]
    assert ids == ["slide:2:title", "slide:2:body", "slide:2:notes"]


def test_deck_route_reads_outline_and_matching_slides() -> None:
    state = GraphState(template="answer", deck=deck(), slide=1, question="notes 3", route=Route("deck"))
    ids = [b.id for b in assemble(state, Ports()).delta["blocks"]]
    assert ids[0] == "deck:outline"
    assert "slide:3:notes" in ids


def test_unknown_slide_falls_back_to_outline() -> None:
    state = GraphState(template="answer", deck=deck(), slide=9, question="q")
    assert [b.id for b in assemble(state, Ports()).delta["blocks"]] == ["deck:outline"]


def test_answer_needs_a_provider() -> None:
    try:
        answer(GraphState(template="answer"), Ports())
    except RuntimeError as exc:
        assert "provider" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RuntimeError")


def test_persist_without_store_is_a_no_op() -> None:
    assert persist(GraphState(template="answer"), Ports()).delta == {}
