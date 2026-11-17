"""``persist``: always the last node. Saves an ingested deck, then writes the run's trace.

One trace row per earlier step (node, outcome, block ids, milliseconds from the injected clock),
plus a row for persist itself. Answer runs also write a ``query_log`` row for evaluation.
"""

from __future__ import annotations

from typing import Any

from lectern.graph.state import GraphState, NodeResult, Ports
from lectern.models import TraceStep
from lectern.search import bm25


def _total_ms(state: GraphState) -> float | None:
    """Sum of step timings, or ``None`` when the clock was not injected."""
    times = [s.ms for s in state.steps if s.ms is not None]
    return round(sum(times), 3) if times else None


def _bm25_scores(state: GraphState) -> dict[str, float]:
    """BM25 of the question against each assembled block (the retrieval signal the eval needs)."""
    if not state.blocks or not state.question:
        return {}
    scores = bm25(state.question, [b.text for b in state.blocks])
    return {state.blocks[i].id: round(s, 4) for i, s in enumerate(scores) if s > 0}


def persist(state: GraphState, ports: Ports) -> NodeResult:
    store = ports.store
    if store is None:
        return NodeResult()
    delta: dict[str, Any] = {}
    deck_id = state.deck_id
    if state.template == "ingest" and state.deck is not None and state.outcome == "done":
        deck_id = store.add_deck(state.deck)
        delta.update(deck_id=deck_id, deck=state.deck.model_copy(update={"id": deck_id}))
    rows = [
        TraceStep(index=s.index, node=s.node, outcome=s.outcome, block_ids=list(s.block_ids), ms=s.ms)
        for s in state.steps
    ]
    rows.append(TraceStep(index=len(rows), node="persist", outcome="continue"))
    trace_id = store.add_trace(deck_id, state.template, state.agent, state.outcome or "done", rows)
    delta["trace_id"] = trace_id
    if state.template == "answer" and deck_id is not None and ports.query_log is not None:
        ports.query_log.log(
            deck_id=deck_id,
            slide=state.slide,
            question=state.question,
            agent=state.agent,
            outcome=state.outcome or "done",
            answer=state.answer,
            citations=state.citations,
            block_ids=tuple(b.id for b in state.blocks),
            bm25_scores=_bm25_scores(state),
            trace_id=trace_id,
            ms=_total_ms(state),
        )
    return NodeResult(delta)
