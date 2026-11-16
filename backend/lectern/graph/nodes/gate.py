"""``gate``: a pure check that refuses an empty or over-long question before any work is done."""

from __future__ import annotations

from lectern.graph.state import GraphState, Next, NodeResult, Ports
from lectern.models import MAX_QUESTION_CHARS


def gate(state: GraphState, ports: Ports) -> NodeResult:
    question = state.question.strip()
    if not question:
        return NodeResult({"answer": "Please ask a question."}, Next.stop("refused:empty"))
    if len(question) > MAX_QUESTION_CHARS:
        text = f"Please keep questions under {MAX_QUESTION_CHARS} characters."
        return NodeResult({"answer": text}, Next.stop("refused:too_long"))
    return NodeResult({"question": question})
