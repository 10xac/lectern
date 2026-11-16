"""``cite``: keep only the citation markers that name a block in the assembled context.

A marker is ``[block-id]`` in the draft, e.g. ``[slide:4:notes]``. Markers for blocks that were
not in this run's context are removed from the text. If no valid marker is left, the node loops
back to ``answer`` with a hint listing the ids it may cite (the ``revise`` loop). Once the loop
has reached its cap, the agent says it cannot support an answer, with no citations.
"""

from __future__ import annotations

import re

from lectern.graph.state import GraphState, Next, NodeResult, Ports
from lectern.graph.templates import ANSWER

MARKER = re.compile(r"\s*\[([a-z]+(?::[\w.-]+)+)\]")
UNSUPPORTED = "I can't support that from this deck."


def clean(draft: str, allowed: set[str]) -> str:
    """The draft without markers that name blocks outside ``allowed``."""
    return MARKER.sub(lambda m: m.group(0) if m.group(1) in allowed else "", draft).strip()


def cite(state: GraphState, ports: Ports) -> NodeResult:
    allowed = {b.id for b in state.blocks}
    found = MARKER.findall(state.draft)
    kept = tuple(dict.fromkeys(m for m in found if m in allowed))  # unique, first-seen order
    if kept:
        return NodeResult({"answer": clean(state.draft, allowed), "citations": kept})
    if state.counters.get("revise", 0) < ANSWER.loop("revise").cap:
        hint = "Cite only from these block ids: " + ", ".join(b.id for b in state.blocks)
        return NodeResult({"hint": hint}, Next.loop("revise"))
    return NodeResult({"answer": UNSUPPORTED, "citations": ()}, Next.stop("unsupported"))
