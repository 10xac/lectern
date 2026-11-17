"""route: rules, the deck agent, and at most one handoff."""

from collections.abc import Sequence

import pytest

from lectern.graph.nodes.route import rules
from lectern.graph.state import Block, Route
from lectern.models import Deck
from lectern.providers.fake import FakeProvider
from lectern.service import ask
from lectern.store import Store


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What does slide 3 say?", Route("other_slide", 3)),
        ("compare with slide #2", Route("other_slide", 2)),
        ("Summarise the deck", Route("deck")),
        ("What is the whole talk about?", Route("deck")),
        ("Explain this", Route("this_slide")),
        ("What about slide 1?", Route("this_slide")),  # the current slide
        ("What about slide 99?", Route("this_slide")),  # no such slide
        ("what are the core ideas of the slide?", Route("this_slide")),
        ("Why March?", None),
    ],
)
def test_rules(question: str, expected: Route | None) -> None:
    assert rules(question, current=1, size=4) == expected


def test_handoff_to_another_slide(store: Store, html_deck: Deck) -> None:
    answer = ask(store, FakeProvider(), html_deck, 1, "What is inside the group on slide 2?")
    assert answer.agent == "slide-2"
    trace = store.get_trace(answer.trace_id or 0)
    assert trace is not None
    assert [s.node for s in trace.steps] == [
        "gate",
        "route",
        "route",
        "assemble",
        "answer",
        "cite",
        "persist",
    ]
    assert trace.steps[1].outcome == "loop:handoff"


def test_second_handoff_is_refused(store: Store, html_deck: Deck) -> None:
    answer = ask(store, FakeProvider(), html_deck, 1, "Compare slide 2 with slide 3")
    assert answer.agent == "slide-2"
    trace = store.get_trace(answer.trace_id or 0)
    assert trace is not None
    assert [s.node for s in trace.steps].count("route") == 2


def test_deck_question_goes_to_the_deck_agent(store: Store, html_deck: Deck) -> None:
    answer = ask(store, FakeProvider(), html_deck, 2, "Summarise the deck for me")
    assert answer.agent == "deck"
    trace = store.get_trace(answer.trace_id or 0)
    assert trace is not None
    assert next(s.block_ids for s in trace.steps if s.node == "assemble")[0] == "deck:outline"


class Router:
    """A stand-in for a real model: replies with a fixed route."""

    name = "router"

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls = 0

    def complete(self, system: str, blocks: Sequence[Block], question: str) -> str:
        self.calls += 1
        if system.startswith("Route"):
            return self.reply
        return f"From the context. [{blocks[0].id}]"


@pytest.mark.parametrize(("reply", "agent"), [("slide 3", "slide-3"), ("deck", "deck"), ("this", "slide-1")])
def test_a_real_model_routes_when_rules_abstain(
    store: Store, html_deck: Deck, reply: str, agent: str
) -> None:
    answer = ask(store, Router(reply), html_deck, 1, "Why March?")
    assert answer.agent == agent


def test_the_fake_provider_never_routes(store: Store, html_deck: Deck) -> None:
    assert ask(store, FakeProvider(), html_deck, 1, "Why March?").agent == "slide-1"
