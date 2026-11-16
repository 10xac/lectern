"""Researchers: one agent instance per source, run in parallel for one job.

Each researcher reads one source with a small tool loop, answers from what it found and reports
``(answer, r, g, evidence)`` (see ``docs/confidence.md``):

* **K**: the trusted base: the deck's slides, notes and attachments (BM25).
* **M**: lectern's memory: past answered questions on this deck (BM25).
* **P**: the model's own knowledge, closed-book (skipped for the ``fake`` model, which has none).
* **W**: the open web (Exa); see ``web.py``.

Researchers are plain functions run in worker threads; every tool call goes through ``ToolCalls``,
the job's shared budget.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from lectern.dna import DNA
from lectern.dna.graph import search_blocks
from lectern.graph.state import Block
from lectern.http import Http
from lectern.jobs.rows import JobRows
from lectern.models import Deck, SourceName, SourceReport
from lectern.providers.base import Provider
from lectern.search import bm25, search_attachments, search_slides, tokenize, top_k

TOP = 4
MARKER = re.compile(r"\[[a-z]+(?::[\w.-]+)+\]")
STOP = set(
    "about after also and are been but can could did does for from had has have how its not "
    "that the their them then there these they this was were what when where which who why will "
    "with would you your".split()
)
CLOSED_BOOK = "Answer from your own knowledge in one or two sentences. If you do not know, say so."


class OutOfCalls(RuntimeError):
    """The job's tool-call budget is spent."""


@dataclass
class ToolCalls:
    """The job's tool-call budget, shared by its researchers (threads)."""

    limit: int
    used: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def take(self) -> None:
        with self._lock:
            if self.used >= self.limit:
                raise OutOfCalls("tool-call budget spent")
            self.used += 1


@dataclass(frozen=True)
class Context:
    """What every researcher of one job may read."""

    deck: Deck
    slide: int | None
    question: str
    provider: Provider
    rows: JobRows
    http: Http
    env: Mapping[str, str] = field(default_factory=dict, repr=False)
    dna: DNA | None = None


Found = tuple[SourceReport, list[Block]]
Researcher = Callable[[Context, ToolCalls], Found]


def terms(text: str) -> set[str]:
    """Content words, without citation markers or stop words."""
    return {t for t in tokenize(MARKER.sub(" ", text)) if t not in STOP and len(t) > 2}


def k_ghost(score: float) -> float:
    """K's ghost mass from its best BM25 score: a strong match means the deck very likely holds it."""
    return round(max(0.05, 1 - score / (score + 2)), 3)


def answer_from(ctx: Context, blocks: list[Block], system: str = "Answer from these blocks only.") -> str:
    return ctx.provider.complete(system, blocks, ctx.question) if blocks else ""


def research_k(ctx: Context, calls: ToolCalls) -> Found:
    calls.take()  # deck_search
    deck = ctx.deck
    query = ctx.question  # the question alone: the slide's own text is always in the answer's context anyway
    slides = [deck.slide(n) for n in search_slides(deck, query, TOP)]
    best = max(bm25(query, [f"{s.title}\n{s.body}\n{s.notes}" for s in deck.slides]), default=0.0)
    blocks = [
        Block(f"slide:{s.n}:{part}", text)
        for s in slides
        if s is not None
        for part, text in (("body", s.body), ("notes", s.notes))
        if text
    ]
    if ctx.deck.id is not None:
        chunks = search_attachments(ctx.rows.store, ctx.deck.id, query, TOP)
        blocks += [Block(f"att:{c.attachment_id}:{c.index}", c.text) for c in chunks]
    g = k_ghost(best)
    if ctx.dna is not None:  # the DNA and its references are part of the trusted base, weighted by degree
        dna = search_blocks(ctx.dna, deck, ctx.slide, ctx.question)
        blocks = dna + blocks
        g = min(g, 0.3) if dna else g
    return report("K", ctx, blocks, calls=1, r=0.9, g_hit=g), blocks


def research_m(ctx: Context, calls: ToolCalls) -> Found:
    calls.take()  # memory_search
    past = ctx.rows.answered(ctx.deck.id or 0)
    docs = [f"{j.question}\n{j.answer.answer if j.answer else ''}" for j in past]
    hits = top_k(ctx.question, docs, TOP)
    blocks = [Block(f"mem:{past[i].id}", docs[i]) for i in hits]
    ups = sum(1 for i in hits if past[i].feedback == 1)
    downs = sum(1 for i in hits if past[i].feedback == -1)
    r = 0.3 + 0.6 * (1 + ups) / (2 + ups + downs)  # memory's track record on similar questions
    return report("M", ctx, blocks, calls=1, r=round(r, 3), g_hit=0.5), blocks


def research_p(ctx: Context, calls: ToolCalls) -> Found:
    calls.take()  # the model itself
    text = ctx.provider.complete(CLOSED_BOOK, [], ctx.question)
    block = Block("model:closed-book", text)
    rep = SourceReport(
        source="P", status="done", answer=text, r=0.5, g=0.5, block_ids=[block.id], tool_calls=1
    )
    return rep, [block]


def report(
    source: SourceName, ctx: Context, blocks: list[Block], calls: int, r: float, g_hit: float
) -> SourceReport:
    """A researcher's report. With no evidence the source most likely does not hold the answer."""
    return SourceReport(
        source=source,
        status="done",
        reason="" if blocks else "nothing matched",
        answer=answer_from(ctx, blocks),
        r=r,
        g=g_hit if blocks else 0.95,
        block_ids=[b.id for b in blocks],
        tool_calls=calls,
    )


def skipped(source: SourceName, reason: str) -> SourceReport:
    return SourceReport(source=source, status="skipped", reason=reason)


RESEARCHERS: dict[SourceName, Researcher] = {"K": research_k, "M": research_m, "P": research_p}
