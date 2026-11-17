"""``assemble``: build the context blocks an agent answers from, then fit them to a budget.

Block ids are stable, so an answer can cite them and the trace can show them:
``slide:<n>:title``, ``slide:<n>:body``, ``slide:<n>:notes``, ``deck:outline`` and
``att:<attachment>:<chunk>``.

A slide agent's budget order is: the current slide, its notes, this deck's attachments (the top
BM25 chunks), the neighbouring slides, then the outline. Blocks are taken in that order while
they fit; one that does not fit is skipped and the next is tried. The deck agent reads the
outline, the slides that best match the question, then attachments. A job's research evidence
comes second in both orders, except past answers (``mem:``), which come last: they are
conversation, not sources. A block that is already in is not added twice.
"""

from __future__ import annotations

from lectern.graph.state import Block, GraphState, NodeResult, Ports
from lectern.models import Deck, Slide
from lectern.search import search_attachments, search_slides

TOP_ATTACHMENTS = 3
TOP_SLIDES = 3


def slide_blocks(slide: Slide, parts: tuple[str, ...] = ("title", "body")) -> list[Block]:
    """The non-empty parts of a slide as blocks."""
    texts = {"title": slide.title, "body": slide.body, "notes": slide.notes}
    return [Block(f"slide:{slide.n}:{p}", texts[p]) for p in parts if texts[p]]


def attachment_blocks(state: GraphState, ports: Ports, query: str) -> list[Block]:
    if ports.store is None or state.deck_id is None:
        return []
    chunks = search_attachments(ports.store, state.deck_id, query, TOP_ATTACHMENTS)
    return [Block(f"att:{c.attachment_id}:{c.index}", c.text) for c in chunks]


def outline_block(deck: Deck) -> list[Block]:
    return [Block("deck:outline", deck.outline)] if deck.outline else []


def fit(groups: list[list[Block]], budget: int) -> tuple[Block, ...]:
    """Take blocks group by group, in order, while they fit in ``budget`` characters."""
    kept: list[Block] = []
    used = 0
    for group in groups:
        for block in group:
            if block not in kept and used + len(block.text) <= budget:
                kept.append(block)
                used += len(block.text)
    return tuple(kept)


def slide_groups(state: GraphState, ports: Ports, deck: Deck) -> list[list[Block]]:
    slide = deck.slide(state.slide)
    if slide is None:
        return [outline_block(deck)]
    neighbours = [b for n in (slide.n - 1, slide.n + 1) if (s := deck.slide(n)) for b in slide_blocks(s)]
    return [
        slide_blocks(slide),
        slide_blocks(slide, ("notes",)),
        attachment_blocks(state, ports, f"{state.question} {slide.title}"),
        neighbours,
        outline_block(deck),
    ]


def deck_groups(state: GraphState, ports: Ports, deck: Deck) -> list[list[Block]]:
    best = [deck.slide(n) for n in search_slides(deck, state.question, TOP_SLIDES)]
    return [
        outline_block(deck),
        [b for s in best if s is not None for b in slide_blocks(s, ("title", "body", "notes"))],
        attachment_blocks(state, ports, state.question),
    ]


def assemble(state: GraphState, ports: Ports) -> NodeResult:
    deck = state.deck
    assert deck is not None
    by_deck = state.route is not None and state.route.kind == "deck"
    groups = deck_groups(state, ports, deck) if by_deck else slide_groups(state, ports, deck)
    if state.evidence:  # research results come right after the slide (or the outline) itself,
        found = [b for b in state.evidence if not b.id.startswith("mem:")]
        groups.insert(1, found)
        groups.append([b for b in state.evidence if b.id.startswith("mem:")])  # past answers: last
    return NodeResult({"blocks": fit(groups, state.budget)})
