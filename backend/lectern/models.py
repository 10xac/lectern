"""The data model shared by ingest, the store, the graph and the API.

Slides are numbered from 1, the way a presenter says "slide 4". A citation names a context
block id (see ``docs/glossary.md``): ``slide:<n>:title|body|notes``, ``deck:outline`` or
``att:<attachment>:<chunk>``.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SourceKind = Literal["html", "pptx", "gslides", "folder"]  # folder: one file per slide
AgentName = str  # "slide-<n>" or "deck"

MAX_QUESTION_CHARS = 1000


class Slide(BaseModel):
    """One slide: its text, its presenter notes and, for HTML decks, its own markup."""

    n: int
    title: str = ""
    body: str = ""
    notes: str = ""
    html: str | None = None
    persona: str | None = None
    agent: dict[str, Any] | None = None  # this slide's AgentSpec layer
    file_id: str | None = None  # in a folder deck, the slide's own file
    ref: str | None = None  # an uploaded deck's lasting slide id, once slides were moved or added


class Deck(BaseModel):
    """A deck after ingest. ``id`` is ``None`` until the store saves it."""

    id: int | None = None
    title: str
    source: SourceKind
    persona: str | None = None
    agent: dict[str, Any] | None = None  # the deck's AgentSpec layer
    file_id: str | None = None  # an uploaded deck's original file
    folder: str | None = None  # a folder deck's path prefix
    visibility: Literal["private", "public", "password"] = "private"  # who may see it (decision D14)
    outline: str = ""
    shell: str | None = None  # an HTML deck's document around one slide (its head, fonts, scripts)
    slides: list[Slide] = Field(default_factory=list)

    def slide(self, n: int) -> Slide | None:
        """The slide numbered ``n``, or ``None`` when the deck has no such slide."""
        return next((s for s in self.slides if s.n == n), None)

    def slide_ref(self, slide: Slide) -> str:
        """A slide's lasting id: its own file id (folder decks), else ``<deck file id>#<n>``."""
        return slide.file_id or slide.ref or f"{self.file_id or f'deck-{self.id}'}#{slide.n}"

    def slide_by_ref(self, ref: str) -> Slide | None:
        return next((s for s in self.slides if self.slide_ref(s) == ref), None)


class Attachment(BaseModel):
    """Data the author uploaded for a deck (text, Markdown or CSV)."""

    id: int
    deck_id: int
    name: str
    chunks: int = 0


class Chunk(BaseModel):
    """A searchable piece of an attachment."""

    attachment_id: int
    deck_id: int
    index: int
    text: str


class Turn(BaseModel):
    """One earlier message in a slide chat."""

    role: Literal["user", "agent"]
    text: str


class Question(BaseModel):
    """The body of ``POST /decks/{id}/slides/{n}/ask``."""

    question: str
    history: list[Turn] = Field(default_factory=list)


class Citation(BaseModel):
    """A block the answer used. ``slide`` or ``attachment`` says where a citation chip jumps."""

    block_id: str
    slide: int | None = None
    attachment: int | None = None
    influence: str | None = None  # a DNA record the answer used: the chip opens it
    file: str | None = None  # a reference file (``file:<id>:p<page>``)


class Answer(BaseModel):
    """What a slide (or the deck) agent says, which agent said it, and the trace of the run."""

    answer: str
    citations: list[Citation] = Field(default_factory=list)
    agent: AgentName
    trace_id: int | None = None
    outcome: str = "answered"
    confidence: dict[str, Any] | None = None  # a job's per-source and fused confidence (see jobs/steps.py)


class TraceStep(BaseModel):
    """One row of a trace: a node execution."""

    index: int
    node: str
    outcome: str
    block_ids: list[str] = Field(default_factory=list)
    ms: float | None = None


class Trace(BaseModel):
    """A stored graph run."""

    id: int
    deck_id: int | None
    template: str
    agent: str
    outcome: str
    steps: list[TraceStep] = Field(default_factory=list)


def citation_for(block_id: str) -> Citation:
    """Turn a block id into a citation that knows where to jump."""
    parts = block_id.split(":")
    if parts[0] == "slide" and len(parts) >= 2 and parts[1].isdigit():
        return Citation(block_id=block_id, slide=int(parts[1]))
    if parts[0] == "att" and len(parts) >= 2 and parts[1].isdigit():
        return Citation(block_id=block_id, attachment=int(parts[1]))
    if parts[0] == "dna" and len(parts) >= 2:
        return Citation(block_id=block_id, influence=parts[1])
    if parts[0] == "file" and len(parts) >= 2:
        return Citation(block_id=block_id, file=parts[1])
    return Citation(block_id=block_id)


class IngestError(ValueError):
    """A deck or attachment that cannot be read; the API answers 422 with the message."""


SourceName = Literal["P", "W", "K", "M"]
JobStatus = Literal[
    "queued", "triaging", "researching", "fusing", "answered", "abstained", "asked", "failed", "cancelled"
]
TERMINAL: frozenset[str] = frozenset({"answered", "abstained", "asked", "failed", "cancelled"})


class SourceReport(BaseModel):
    """What one researcher did: its source, how it ended, its answer and its confidence terms."""

    source: SourceName
    status: Literal["done", "skipped", "failed", "timeout"]
    reason: str = ""
    answer: str = ""
    r: float = 0.0  # reliability given the answer is in this source's corpus
    g: float = 1.0  # ghost mass: probability the answer is not in the corpus at all
    block_ids: list[str] = Field(default_factory=list)
    tool_calls: int = 0


class Job(BaseModel):
    """One asynchronous question, answered on its own slide (``slide=None``: the deck)."""

    id: str
    deck_id: int
    slide: int | None
    question: str
    status: JobStatus = "queued"
    answer: Answer | None = None
    sources: list[SourceReport] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)  # e.g. "ran out of time"
    error: str | None = None
    feedback: int | None = None  # +1 or -1: a reader's verdict on the answer (feeds memory's r)
    viewer: str = ""  # whose thread the question and answer belong to (a user, or an anonymous visitor)


class JobEvent(BaseModel):
    """One step of a job's progress, as the SSE stream sends it (``seq`` is the event id)."""

    seq: int
    kind: str
    data: dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    """One turn in a slide's (or the deck's) thread."""

    id: int
    deck_id: int
    slide: int | None
    role: Literal["user", "agent"]
    text: str
    job_id: str | None = None
    answer: Answer | None = None
