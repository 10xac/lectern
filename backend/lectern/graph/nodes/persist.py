"""``persist``: always the last node. Saves an ingested deck, then writes the run's trace.

One trace row per earlier step (node, outcome, block ids, milliseconds from the injected clock),
plus a row for persist itself.
"""

from __future__ import annotations

from typing import Any

from lectern.graph.state import GraphState, NodeResult, Ports
from lectern.models import TraceStep


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
    delta["trace_id"] = store.add_trace(deck_id, state.template, state.agent, state.outcome or "done", rows)
    return NodeResult(delta)
