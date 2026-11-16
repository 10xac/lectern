"""The deterministic graph runner.

Modelled on a larger agent-graph runner, at teaching size:

* nodes run in template order; a node's ``next`` may continue, stop with an outcome, or take
  one of the template's declared loops (any other move is refused);
* every loop has a counter in the state and a cap in the template, and the whole run has a hard
  step cap, so no node can make the graph spin;
* an exception inside a node becomes the outcome ``error:<node>.<ExceptionType>``;
* the template's ``final`` node (``persist``) always runs last, exactly once, whatever happened.
  It sees every earlier step in ``state.steps``. If it fails, the failure is recorded on its own
  step and the run's outcome does not change.

Determinism: the path depends only on the template and the node results. Timing is measured
only when the caller injects ``clock``, and is used only for the trace.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from lectern.graph.state import GraphState, Next, NodeFn, NodeResult, Ports, Step
from lectern.graph.templates import Template

DONE = "done"


@dataclass(frozen=True)
class GraphRun:
    """The final state and every step, in order."""

    state: GraphState
    steps: tuple[Step, ...]

    @property
    def path(self) -> tuple[str, ...]:
        return tuple(s.node for s in self.steps)

    @property
    def outcome(self) -> str:
        return self.state.outcome or DONE


class Refused(RuntimeError):
    """A node asked for a move the template does not allow."""


def _block_ids(state: GraphState, delta: Mapping[str, object]) -> tuple[str, ...]:
    if "blocks" in delta:
        return tuple(b.id for b in state.blocks)
    if "citations" in delta:
        return state.citations
    return ()


def _execute(
    name: str, fn: NodeFn, state: GraphState, ports: Ports, clock: Callable[[], float] | None, index: int
) -> tuple[GraphState, Next | None, Step]:
    """Run one node. Returns the new state, its move (``None`` on error) and its trace step."""
    started = clock() if clock else None
    try:
        result = fn(state, ports)
        if not isinstance(result, NodeResult):
            raise Refused(f"{name} returned {type(result).__name__}")
        new_state = state.apply(result.delta)
        nxt: Next | None = result.next
        label = result.next.label
        ids = _block_ids(new_state, result.delta)
    except Exception as exc:  # a node failure is an outcome, never an escape
        new_state, nxt, label, ids = state, None, f"error:{name}.{type(exc).__name__}", ()
    ms = round((clock() - started) * 1000, 3) if clock and started is not None else None
    return new_state, nxt, Step(index=index, node=name, outcome=label, block_ids=ids, ms=ms)


def _take_loop(template: Template, state: GraphState, node: str, nxt: Next) -> tuple[int, GraphState]:
    """The position a loop jumps to, and the state with its counter raised."""
    loop = next((lp for lp in template.loops if lp.id == nxt.target and lp.source == node), None)
    if loop is None:
        raise Refused(f"{node} has no loop {nxt.target}")
    count = state.counters.get(loop.id, 0)
    if count >= loop.cap:
        raise Refused(f"loop {loop.id} reached its cap of {loop.cap}")
    counters = MappingProxyType({**state.counters, loop.id: count + 1})
    return template.nodes.index(loop.target), state.apply({"counters": counters})


def run(
    template: Template,
    state: GraphState,
    nodes: Mapping[str, NodeFn],
    ports: Ports | None = None,
    *,
    clock: Callable[[], float] | None = None,
    max_steps: int | None = None,
) -> GraphRun:
    """Run ``template`` from ``state`` with the node implementations in ``nodes``.

    ``max_steps`` can only lower the template's own step cap.
    """
    missing = [n for n in template.nodes if n not in nodes]
    if missing:
        raise ValueError(f"no implementation for nodes {missing}")
    ports = ports or Ports()
    cap = template.step_cap if max_steps is None else min(max_steps, template.step_cap)
    has_final = template.nodes[-1] == template.final
    body = template.nodes[:-1] if has_final else template.nodes
    steps: list[Step] = []
    at = 0
    while at < len(body) and state.outcome is None:
        if len(steps) >= cap - 1:  # keep one step for the final node
            state = state.apply({"outcome": "step_cap"})
            break
        name = body[at]
        state, nxt, step = _execute(name, nodes[name], state, ports, clock, len(steps))
        steps.append(step)
        if nxt is None:
            state = state.apply({"outcome": step.outcome})
        elif nxt.kind == "stop":
            state = state.apply({"outcome": nxt.target or DONE})
        elif nxt.kind == "loop":
            try:
                at, state = _take_loop(template, state, name, nxt)
            except Refused:
                state = state.apply({"outcome": f"loop_cap:{nxt.target}"})
        else:
            at += 1
    if state.outcome is None:
        state = state.apply({"outcome": DONE})
    if has_final:
        final = template.final
        before = state.apply({"steps": tuple(steps)})
        after, _, step = _execute(final, nodes[final], before, ports, clock, len(steps))
        steps.append(step)
        state = after.apply({"outcome": state.outcome})  # the final node never changes the outcome
    return GraphRun(state=state.apply({"steps": tuple(steps)}), steps=tuple(steps))
