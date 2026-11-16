"""The ``ingest`` template's nodes: detect → parse → normalise → index (then persist).

A file that cannot be read stops the run with the outcome ``refused: <reason>``.
"""

from __future__ import annotations

from lectern.graph.state import GraphState, Next, NodeResult, Ports
from lectern.ingest import ADAPTERS
from lectern.ingest import detect as sniff
from lectern.models import IngestError, Slide

MAX_SLIDES = 200


def detect(state: GraphState, ports: Ports) -> NodeResult:
    try:
        return NodeResult({"kind": sniff(state.filename, state.data)})
    except IngestError as exc:
        return NodeResult(next=Next.stop(f"refused: {exc}"))


def parse(state: GraphState, ports: Ports) -> NodeResult:
    assert state.kind is not None  # detect always sets it or stops
    try:
        deck = ADAPTERS[state.kind](state.data, state.filename)
    except IngestError as exc:
        return NodeResult(next=Next.stop(f"refused: {exc}"))
    return NodeResult({"deck": deck, "data": b""})  # the bytes are not needed past parse


def normalise(state: GraphState, ports: Ports) -> NodeResult:
    """Trim every field, number slides 1..N and enforce the slide cap."""
    deck = state.deck
    assert deck is not None
    if not deck.slides:
        return NodeResult(next=Next.stop("refused: the deck has no slides"))
    if len(deck.slides) > MAX_SLIDES:
        return NodeResult(next=Next.stop(f"refused: more than {MAX_SLIDES} slides"))
    slides = [
        Slide(
            n=i,
            title=s.title.strip(),
            body=s.body.strip(),
            notes=s.notes.strip(),
            html=s.html,
            persona=s.persona,
            agent=s.agent,
        )
        for i, s in enumerate(deck.slides, start=1)
    ]
    return NodeResult({"deck": deck.model_copy(update={"title": deck.title.strip(), "slides": slides})})


def label(slide: Slide) -> str:
    """How a slide appears in the outline: its title, else its first line."""
    return slide.title or next(iter(slide.body.splitlines()), "") or "(untitled)"


def index(state: GraphState, ports: Ports) -> NodeResult:
    """Build the deck outline, which the deck agent and every slide agent can read."""
    deck = state.deck
    assert deck is not None
    outline = "\n".join(f"{s.n}. {label(s)}" for s in deck.slides)
    return NodeResult({"deck": deck.model_copy(update={"outline": outline})})
