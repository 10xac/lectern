"""``answer``: ask the provider, with the persona, recent chat turns and any revise hint."""

from __future__ import annotations

from lectern.graph.state import GraphState, NodeResult, Ports


def system_prompt(state: GraphState) -> str:
    parts = [state.persona]
    if state.history:
        parts.append("Earlier in this chat:\n" + "\n".join(state.history))
    if state.hint:
        parts.append(state.hint)
    return "\n\n".join(p for p in parts if p)


def answer(state: GraphState, ports: Ports) -> NodeResult:
    provider = ports.model_for(state.model)
    if provider is None:
        raise RuntimeError("the answer node needs a provider")
    draft = provider.complete(system_prompt(state), state.blocks, state.question)
    return NodeResult({"draft": draft})
