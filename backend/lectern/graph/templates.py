"""The two graph templates. They are code, not configuration: a fixed chain of named nodes, the
backward edges it may take (each with a cap), and the node that always runs last.

    ingest: detect → parse → normalise → index → persist
    answer: gate → route → assemble → answer → cite → persist
            route → route   (handoff: another slide's agent takes over, at most once)
            cite  → answer  (revise: the draft cited a block that is not in context, at most twice)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Loop:
    """A declared backward edge from ``source`` to ``target``, taken at most ``cap`` times."""

    id: str
    source: str
    target: str
    cap: int


@dataclass(frozen=True)
class Template:
    """An ordered chain of nodes whose last node (``final``) always runs, once."""

    id: str
    nodes: tuple[str, ...]
    loops: tuple[Loop, ...] = ()
    final: str = "persist"

    @property
    def step_cap(self) -> int:
        """The hard limit on steps: every node once, every loop to its cap, plus one spare."""
        return len(self.nodes) + sum(lp.cap * self._span(lp) for lp in self.loops) + 1

    def _span(self, loop: Loop) -> int:
        return self.nodes.index(loop.source) - self.nodes.index(loop.target) + 1

    def loop(self, loop_id: str) -> Loop:
        return next(lp for lp in self.loops if lp.id == loop_id)


HANDOFF_CAP = 1
REVISE_CAP = 2

INGEST = Template("ingest", ("detect", "parse", "normalise", "index", "persist"))

ANSWER = Template(
    "answer",
    ("gate", "route", "assemble", "answer", "cite", "persist"),
    loops=(
        Loop("handoff", source="route", target="route", cap=HANDOFF_CAP),
        Loop("revise", source="cite", target="answer", cap=REVISE_CAP),
    ),
)

TEMPLATES = {t.id: t for t in (INGEST, ANSWER)}
