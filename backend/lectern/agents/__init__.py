"""Slide agents and the deck agent, each an instance of one ``AgentSpec`` plus its overrides.

Every agent runs the same graph; what differs is its resolved spec (persona, model, tools, budget)
and the context the ``assemble`` node builds for it. See ``spec.py`` for the layers. A slide's
``persona`` (``data-persona``) and ``agent`` (``data-agent``) are its layer; the deck's are the
deck layer.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from lectern.agents.spec import (
    AgentSpec,
    RequestAgent,
    Resolved,
    apply_request,
    env_layer,
    merge_layers,
    packaged_default,
)
from lectern.models import Deck

DECK_PERSONA = "You are the agent for a whole presentation. Answer questions that span its slides."
DECK_AGENT = "deck"


@dataclass(frozen=True)
class AgentConfig:
    """Who answers: an agent name, its slide (``None`` for the deck agent) and its resolved spec."""

    name: str
    slide: int | None
    resolved: Resolved

    @property
    def spec(self) -> AgentSpec:
        return self.resolved.spec

    @property
    def persona(self) -> str:
        return self.resolved.spec.persona


def layer(agent: Mapping[str, Any] | None, persona: str | None) -> dict[str, Any]:
    """One stored layer: its ``agent`` object, with a ``persona`` attribute on top when set."""
    out = dict(agent or {})
    if persona:
        out["persona"] = persona
    return out


WEB_TOOLS = ("web_search", "fetch_url")


def resolve(
    deck: Deck,
    n: int | None,
    request: RequestAgent | None = None,
    env: Mapping[str, str] | None = None,
) -> Resolved:
    """The effective spec for slide ``n`` (``None``: the deck agent)."""
    env = os.environ if env is None else env
    base = packaged_default()
    if n is None:
        base = base | {"id": DECK_AGENT, "persona": DECK_PERSONA}
    from_env = env_layer(env)
    if env.get("EXA_API_KEY"):  # a web key is set: the web researcher (W) may run, as triage routes it
        from_env |= {"tools": [*base["tools"], *(t for t in WEB_TOOLS if t not in base["tools"])]}
    layers: list[tuple[str, Mapping[str, Any] | None]] = [
        ("default", base),
        ("env", from_env),
        ("deck", layer(deck.agent, deck.persona)),
    ]
    slide = deck.slide(n) if n is not None else None
    if slide is not None:
        layers.append(("slide", layer(slide.agent, slide.persona)))
    return apply_request(merge_layers(layers), request, env)


def slide_agent(deck: Deck, n: int, request: RequestAgent | None = None) -> AgentConfig:
    return AgentConfig(name=f"slide-{n}", slide=n, resolved=resolve(deck, n, request))


def deck_agent(deck: Deck, request: RequestAgent | None = None) -> AgentConfig:
    return AgentConfig(name=DECK_AGENT, slide=None, resolved=resolve(deck, None, request))
