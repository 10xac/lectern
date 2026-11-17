"""The graph's frozen state and what a node gives back.

Modelled on a larger agent-graph runner: the state is immutable, a node never changes it in
place but returns a ``NodeResult`` whose ``delta`` the runner applies, and ``next`` tells the
runner where to go (``continue``, ``stop`` with an outcome, or ``loop`` along a declared edge).
Nodes do their I/O only through ``Ports``, so a test can hand them a fake store or provider.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, fields, replace
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal

from lectern.agents.spec import ModelBinding, RequestAgent
from lectern.models import Deck, SourceKind

if TYPE_CHECKING:
    from lectern.providers.base import Provider
    from lectern.store import Store


@dataclass(frozen=True)
class Block:
    """A piece of context with a stable id, e.g. ``slide:4:notes`` or ``att:2:0``."""

    id: str
    text: str


@dataclass(frozen=True)
class Route:
    """Who should answer: this slide's agent, another slide's agent, or the deck agent."""

    kind: Literal["this_slide", "other_slide", "deck"]
    slide: int | None = None


@dataclass(frozen=True)
class Next:
    """Where the runner goes after a node."""

    kind: Literal["continue", "stop", "loop"] = "continue"
    target: str | None = None  # the outcome for stop, the loop id for loop

    @staticmethod
    def stop(outcome: str) -> Next:
        return Next("stop", outcome)

    @staticmethod
    def loop(loop_id: str) -> Next:
        return Next("loop", loop_id)

    @property
    def label(self) -> str:
        return self.kind if self.target is None else f"{self.kind}:{self.target}"


CONTINUE = Next()


@dataclass(frozen=True)
class Step:
    """One node execution, as the trace records it."""

    index: int
    node: str
    outcome: str
    block_ids: tuple[str, ...] = ()
    ms: float | None = None


@dataclass(frozen=True)
class GraphState:
    """Everything a run knows. Ingest uses the first group of fields, answer the second."""

    template: str
    # ingest
    filename: str = ""
    data: bytes = b""
    kind: SourceKind | None = None
    deck: Deck | None = None
    # answer
    deck_id: int | None = None
    slide: int = 1
    question: str = ""
    history: tuple[str, ...] = ()
    agent: str = ""
    persona: str = ""
    model: ModelBinding | None = None  # the answering instance's model binding (no key in it)
    override: RequestAgent | None = None  # the request's agent override, kept across handoffs
    route: Route | None = None
    handoffs: int = 0
    handoff_refused: bool = False
    budget: int = 4000  # characters of context the assemble node may use
    evidence: tuple[Block, ...] = ()  # what a job's researchers found; ``assemble`` includes it
    blocks: tuple[Block, ...] = ()
    hint: str = ""
    draft: str = ""
    answer: str = ""
    citations: tuple[str, ...] = ()
    # bookkeeping (the runner writes these)
    counters: Mapping[str, int] = field(default_factory=lambda: MappingProxyType({}))
    steps: tuple[Step, ...] = ()
    outcome: str | None = None
    trace_id: int | None = None

    def apply(self, delta: Mapping[str, Any]) -> GraphState:
        """A new state with ``delta`` applied; unknown keys are refused."""
        unknown = sorted(set(delta) - STATE_KEYS)
        if unknown:
            raise KeyError(f"unknown state keys {unknown}")
        return replace(self, **delta)


STATE_KEYS = frozenset(f.name for f in fields(GraphState))


@dataclass(frozen=True)
class NodeResult:
    """A node's answer: the fields it changes and where to go next."""

    delta: Mapping[str, Any] = field(default_factory=dict)
    next: Next = CONTINUE


@dataclass(frozen=True)
class Ports:
    """The outside world a node may touch. Pure nodes ignore it."""

    store: Store | None = None
    provider: Provider | None = None
    providers: Callable[[ModelBinding], Provider] | None = None  # one provider per model binding
    query_log: Any = None  # a QueryLog instance, when logging is enabled

    def model_for(self, binding: ModelBinding | None) -> Provider | None:
        """The provider for one instance's binding, else the run's default provider."""
        if self.providers is not None and binding is not None:
            return self.providers(binding)
        return self.provider


NodeFn = Callable[[GraphState, Ports], NodeResult]
