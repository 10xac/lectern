"""The runner: template order, capped loops, the step cap, and persist always last."""

from collections.abc import Callable

import pytest

from lectern.graph.runner import run
from lectern.graph.state import GraphState, Next, NodeFn, NodeResult, Ports
from lectern.graph.templates import ANSWER, INGEST, Loop, Template

T = Template("t", ("a", "b", "c", "persist"), loops=(Loop("again", source="c", target="b", cap=2),))


def recorder(log: list[str], name: str, nxt: Callable[[GraphState], Next] | None = None) -> NodeFn:
    def node(state: GraphState, ports: Ports) -> NodeResult:
        log.append(name)
        return NodeResult({}, nxt(state) if nxt else Next())

    return node


def nodes(log: list[str], **overrides: NodeFn) -> dict[str, NodeFn]:
    table = {n: recorder(log, n) for n in T.nodes}
    table.update(overrides)
    return table


def test_runs_in_template_order() -> None:
    log: list[str] = []
    result = run(T, GraphState(template="t"), nodes(log))
    assert log == ["a", "b", "c", "persist"]
    assert result.path == ("a", "b", "c", "persist")
    assert result.outcome == "done"
    assert [s.index for s in result.steps] == [0, 1, 2, 3]


def test_loop_is_capped() -> None:
    log: list[str] = []
    looping = recorder(log, "c", lambda s: Next.loop("again"))
    result = run(T, GraphState(template="t"), nodes(log, c=looping))
    assert log == ["a", "b", "c", "b", "c", "b", "c", "persist"]
    assert result.outcome == "loop_cap:again"
    assert result.state.counters == {"again": 2}


def test_undeclared_loop_is_refused() -> None:
    log: list[str] = []
    result = run(T, GraphState(template="t"), nodes(log, a=recorder(log, "a", lambda s: Next.loop("again"))))
    assert result.outcome == "loop_cap:again"
    assert result.path == ("a", "persist")


def test_step_cap_stops_and_persist_still_runs() -> None:
    log: list[str] = []
    looping = recorder(log, "c", lambda s: Next.loop("again"))
    result = run(T, GraphState(template="t"), nodes(log, c=looping), max_steps=4)
    assert result.outcome == "step_cap"
    assert result.path == ("a", "b", "c", "persist")


def test_step_caps_of_the_real_templates() -> None:
    assert INGEST.step_cap == 6
    assert ANSWER.step_cap == 6 + 1 * 1 + 2 * 2 + 1


def test_stop_skips_to_persist() -> None:
    log: list[str] = []
    result = run(T, GraphState(template="t"), nodes(log, a=recorder(log, "a", lambda s: Next.stop("nope"))))
    assert result.path == ("a", "persist")
    assert result.outcome == "nope"


def test_exception_becomes_outcome_and_persist_runs() -> None:
    def boom(state: GraphState, ports: Ports) -> NodeResult:
        raise ValueError("bad")

    log: list[str] = []
    result = run(T, GraphState(template="t"), nodes(log, b=boom))
    assert result.outcome == "error:b.ValueError"
    assert result.path == ("a", "b", "persist")
    assert result.steps[1].outcome == "error:b.ValueError"


def test_persist_failure_does_not_change_outcome() -> None:
    def broken(state: GraphState, ports: Ports) -> NodeResult:
        raise OSError("disk full")

    result = run(T, GraphState(template="t"), nodes([], persist=broken))
    assert result.outcome == "done"
    assert result.steps[-1].outcome == "error:persist.OSError"


def test_persist_sees_earlier_steps_and_cannot_change_outcome() -> None:
    seen: list[tuple[str, ...]] = []

    def persist(state: GraphState, ports: Ports) -> NodeResult:
        seen.append(tuple(s.node for s in state.steps))
        return NodeResult({"outcome": "rewritten"})

    result = run(T, GraphState(template="t"), nodes([], persist=persist))
    assert seen == [("a", "b", "c")]
    assert result.outcome == "done"


def test_bad_results_and_unknown_keys_are_errors() -> None:
    bad: NodeFn = lambda s, p: "nope"  # type: ignore[assignment,return-value]  # noqa: E731
    unknown: NodeFn = lambda s, p: NodeResult({"no_such_field": 1})  # noqa: E731
    assert run(T, GraphState(template="t"), nodes([], a=bad)).outcome == "error:a.Refused"
    assert run(T, GraphState(template="t"), nodes([], a=unknown)).outcome == "error:a.KeyError"


def test_missing_implementation() -> None:
    with pytest.raises(ValueError, match="no implementation"):
        run(T, GraphState(template="t"), {"a": recorder([], "a")})


def test_timing_comes_from_the_injected_clock() -> None:
    ticks = iter(range(100))
    result = run(T, GraphState(template="t"), nodes([]), clock=lambda: float(next(ticks)))
    assert [s.ms for s in result.steps] == [1000.0] * 4
    assert all(s.ms is None for s in run(T, GraphState(template="t"), nodes([])).steps)


def test_template_without_final_node() -> None:
    plain = Template("p", ("a", "b"), final="persist")
    log: list[str] = []
    result = run(plain, GraphState(template="p"), {"a": recorder(log, "a"), "b": recorder(log, "b")})
    assert result.path == ("a", "b")
