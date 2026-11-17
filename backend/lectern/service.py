"""The entry points the API and the CLI share: ingest a deck, attach data, ask a slide.

Each one builds the starting state, runs a template and turns the final state into a model.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from lectern.agents import deck_agent, resolve, slide_agent
from lectern.agents.spec import ModelBinding, RequestAgent
from lectern.graph.nodes import ANSWER_NODES, INGEST_NODES
from lectern.graph.runner import GraphRun, run
from lectern.graph.state import Block, GraphState, Ports, Route
from lectern.graph.templates import ANSWER, INGEST
from lectern.ingest.attachments import chunk
from lectern.models import Answer, Attachment, Deck, Turn, citation_for
from lectern.providers.base import Provider
from lectern.query_log import QueryLog
from lectern.store import Store

HISTORY_TURNS = 6

Clock = Callable[[], float]
ProviderFactory = Callable[[ModelBinding], Provider]


def run_ingest(store: Store, name: str, data: bytes, clock: Clock = time.perf_counter) -> GraphRun:
    """Run the ``ingest`` template on an uploaded file. ``run.state.deck`` is the saved deck."""
    state = GraphState(template=INGEST.id, filename=name, data=data, agent="ingest")
    return run(INGEST, state, INGEST_NODES, Ports(store=store), clock=clock)


def attach(store: Store, deck_id: int, name: str, data: bytes) -> Attachment:
    """Chunk an uploaded file and save it as one of the deck's attachments."""
    return store.add_attachment(deck_id, name, chunk(name, data))


def ask(
    store: Store,
    provider: Provider,
    deck: Deck,
    n: int | None,
    question: str,
    history: Sequence[Turn] = (),
    clock: Clock = time.perf_counter,
    override: RequestAgent | None = None,
    providers: ProviderFactory | None = None,
    evidence: Sequence[Block] = (),
) -> Answer:
    """Ask slide ``n``'s agent a question; it may hand off to another slide or to the deck agent.

    ``n=None`` asks the deck agent. ``evidence`` is what a job's researchers found.
    ``override`` is the request's agent layer. ``providers`` builds one provider per model binding;
    without it every instance uses ``provider``. Raises ``SpecError`` for a refused override.
    """
    agent = slide_agent(deck, n, override) if n is not None else deck_agent(deck, override)
    state = GraphState(
        template=ANSWER.id,
        deck=deck,
        deck_id=deck.id,
        slide=n or 1,
        route=Route("deck") if n is None else None,
        evidence=tuple(evidence),
        question=question,
        history=tuple(f"{t.role}: {t.text}" for t in history[-HISTORY_TURNS:]),
        agent=agent.name,
        persona=agent.persona,
        model=agent.spec.model,
        override=override,
    )
    query_log = QueryLog(store) if store is not None else None
    ports = Ports(store=store, provider=provider, providers=providers, query_log=query_log)
    result = run(ANSWER, state, ANSWER_NODES, ports, clock=clock)
    final = result.state
    return Answer(
        answer=final.answer,
        citations=[citation_for(c) for c in final.citations],
        agent=final.agent,
        trace_id=final.trace_id,
        outcome=result.outcome,
    )


def set_agent(store: Store, deck: Deck, n: int | None, agent: Mapping[str, Any] | None) -> Deck:
    """Store the deck's (``n=None``) or slide ``n``'s agent layer, after checking it resolves.

    Raises ``SpecError`` when the merged spec would be invalid (e.g. an unknown key).
    """
    layer = dict(agent) if agent else None
    if n is None:
        candidate = deck.model_copy(update={"agent": layer})
    else:
        slides = [s.model_copy(update={"agent": layer}) if s.n == n else s for s in deck.slides]
        candidate = deck.model_copy(update={"slides": slides})
    for slide in [None, *(s.n for s in candidate.slides)]:
        resolve(candidate, slide)
    assert deck.id is not None
    store.set_agent(deck.id, n, layer)
    return candidate
