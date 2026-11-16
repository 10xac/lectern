"""``route``: decide who answers — this slide's agent, another slide's agent, or the deck agent.

Rules first (pure): a question that names another slide ("what does slide 5 say?") goes to that
slide's agent; one about the whole deck ("summarise the talk") goes to the deck agent; anything
else stays here. Only when the rules abstain and the provider is a real model is the model asked.

A handoff to another slide loops back to ``route`` as that slide's agent, which may answer
itself or go to the deck agent, but may not hand off again: the second request is refused and
the current agent answers. So two slides never pass a question back and forth.
"""

from __future__ import annotations

import re
from typing import Any

from lectern.agents import AgentConfig, deck_agent, slide_agent
from lectern.graph.state import Block, GraphState, Next, NodeResult, Ports, Route
from lectern.graph.templates import HANDOFF_CAP
from lectern.providers.base import Provider

SLIDE_REF = re.compile(r"\bslide\s*#?\s*(\d+)", re.IGNORECASE)
DECK_WORDS = re.compile(
    r"\b(deck|presentation|talk|overall|whole|all (the )?slides|every slide|agenda|summari[sz]e|summary)\b",
    re.IGNORECASE,
)
HERE_WORDS = re.compile(r"\b(this|here|current)\b", re.IGNORECASE)


def rules(question: str, current: int, size: int) -> Route | None:
    """The rule-based decision, or ``None`` when the rules have no opinion."""
    for match in SLIDE_REF.finditer(question):
        n = int(match.group(1))
        if n != current and 1 <= n <= size:
            return Route("other_slide", n)
    if DECK_WORDS.search(question):
        return Route("deck")
    if SLIDE_REF.search(question) or HERE_WORDS.search(question):
        return Route("this_slide")
    return None


def ask_model(provider: Provider, outline: str, question: str, current: int, size: int) -> Route:
    """Let a real model route: it must reply ``this``, ``deck`` or ``slide <n>``."""
    system = "Route the question. Reply with exactly one of: this, deck, slide <n>."
    reply = provider.complete(system, [Block("deck:outline", outline)], question).strip().lower()
    match = SLIDE_REF.search(reply)
    if match and int(match.group(1)) != current and 1 <= int(match.group(1)) <= size:
        return Route("other_slide", int(match.group(1)))
    return Route("deck") if reply.startswith("deck") else Route("this_slide")


def instance(agent: AgentConfig) -> dict[str, Any]:
    """The state fields that say which agent instance answers."""
    return {"agent": agent.name, "persona": agent.persona, "model": agent.spec.model}


def route(state: GraphState, ports: Ports) -> NodeResult:
    deck = state.deck
    assert deck is not None
    if state.route == Route("deck"):  # a question asked of the deck itself stays with the deck agent
        return NodeResult(instance(deck_agent(deck, state.override)))
    size = len(deck.slides)
    decision = rules(state.question, state.slide, size)
    provider = ports.model_for(state.model)
    if decision is None and provider is not None and provider.name != "fake":
        decision = ask_model(provider, deck.outline, state.question, state.slide, size)
    decision = decision or Route("this_slide")
    if decision.kind == "deck":
        agent = deck_agent(deck, state.override)
        return NodeResult({"route": decision, **instance(agent)})
    if decision.kind == "other_slide" and decision.slide is not None:
        if state.handoffs >= HANDOFF_CAP:
            return NodeResult({"route": Route("this_slide"), "handoff_refused": True})
        agent = slide_agent(deck, decision.slide, state.override)
        delta = {
            "route": decision,
            "slide": decision.slide,
            "handoffs": state.handoffs + 1,
            **instance(agent),
        }
        return NodeResult(delta, Next.loop("handoff"))
    return NodeResult({"route": decision})
