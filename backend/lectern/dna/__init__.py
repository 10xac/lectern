"""The conceptual DNA of a deck: influences (ideas, reasoning, notes, citations, references) that
shaped one slide, several slides or the whole deck, each with a degree of influence.

Every surface (web app, REST, MCP, CLI) goes through ``DNA`` here, so a record added by a person in
the drawer and one added by an AI over MCP are the same row shape. Influences refer to slides by
their lasting ids (``Deck.slide_ref``) and to files by registry id, so they survive reordering,
overwrites and renames. Each one remembers the version of every file it was written for.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from lectern.files import FileError, Files
from lectern.models import Deck
from lectern.store import Store

Kind = Literal["idea", "reasoning", "explanation", "note", "citation", "reference"]
Degree = Literal["high", "medium", "low", "general"]
Component = Literal["whole", "text", "image", "chart", "layout", "concept", "element"]
Via = Literal["ui", "api", "mcp", "cli"]
WEIGHT: dict[str, float] = {"high": 1.0, "medium": 0.6, "low": 0.3, "general": 0.2}
SCHEMA = """
CREATE TABLE IF NOT EXISTS influences (
  id TEXT PRIMARY KEY, deck_id INTEGER NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS influence_history (
  influence_id TEXT NOT NULL, at REAL NOT NULL, data TEXT NOT NULL);
"""


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Scope(Strict):
    kind: Literal["slide", "slides", "deck"]
    slides: list[int] = Field(default_factory=list)  # slide numbers as the caller sees them now


class Target(Strict):
    component: Component = "whole"
    element_id: str | None = Field(default=None, max_length=200)
    label: str | None = Field(default=None, max_length=200)


class Ref(Strict):
    type: Literal["url", "file"]
    url: str | None = Field(default=None, max_length=2000)
    file_id: str | None = None
    path: str | None = None  # a convenience on input: resolved to file_id
    label: str | None = Field(default=None, max_length=200)
    quote: str | None = Field(default=None, max_length=2000)


class Author(Strict):
    type: Literal["human", "ai"] = "human"
    name: str = Field(default="anonymous", max_length=100)
    tool: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)


class InfluenceIn(Strict):
    """What a person (the drawer), a script (REST) or an AI tool (MCP) sends."""

    scope: Scope
    target: Target = Target()
    kind: Kind
    degree: Degree
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=10_000)
    refs: list[Ref] = Field(default_factory=list)
    author: Author = Author()
    parent_id: str | None = None


class Influence(InfluenceIn):
    model_config = ConfigDict(extra="ignore")

    id: str
    deck_id: int
    via: Via
    slide_ids: list[str] = Field(default_factory=list)  # lasting ids; ``scope.slides`` is derived
    versions: dict[str, int] = Field(default_factory=dict)  # file id → version it was written for
    created_at: float
    updated_at: float


class InfluencePatch(Strict):
    scope: Scope | None = None
    target: Target | None = None
    kind: Kind | None = None
    degree: Degree | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, max_length=10_000)
    refs: list[Ref] | None = None
    parent_id: str | None = None


class DNA:
    """Influences for decks, stored as JSON rows; every edit keeps the previous version."""

    def __init__(self, store: Store, files: Files, clock: Any = time.time) -> None:
        self.store, self.files, self.clock = store, files, clock
        with store.tx() as db:
            db.executescript(SCHEMA)

    def _deck(self, deck_id: int) -> Deck:
        deck = self.store.get_deck(deck_id)
        if deck is None:
            raise FileError(404, f"no deck {deck_id}")
        return deck

    def _resolve(self, deck: Deck, data: InfluenceIn) -> dict[str, Any]:
        """Slide numbers → lasting ids, ref paths → file ids, and the file versions it was written for."""
        if data.scope.kind == "deck":
            refs_ = []
        else:
            if not data.scope.slides or (data.scope.kind == "slide" and len(data.scope.slides) != 1):
                raise FileError(422, "a slide scope names one slide; a slides scope names one or more")
            missing = [n for n in data.scope.slides if deck.slide(n) is None]
            if missing:
                raise FileError(422, f"deck {deck.id} has no slide(s) {missing}")
            refs_ = [deck.slide_ref(s) for n in data.scope.slides if (s := deck.slide(n))]
        refs = []
        for ref in data.refs:
            if ref.type == "file":
                file = self.files.get(ref.path) if ref.path else self.files.by_id(ref.file_id or "")
                ref = ref.model_copy(update={"file_id": file.id, "path": None})
            elif not ref.url:
                raise FileError(422, "a url reference needs a url")
            refs.append(ref)
        if data.parent_id is not None:
            self.get(deck.id or 0, data.parent_id)
        file_ids = {r.split("#")[0] for r in refs_} | {r.file_id for r in refs if r.file_id}
        file_ids |= {deck.file_id} if deck.file_id and data.scope.kind == "deck" else set()
        versions = {f: self.files.by_id(f).version for f in file_ids if not f.startswith("deck-")}
        return {"slide_ids": refs_, "refs": [r.model_dump() for r in refs], "versions": versions}

    def add(self, deck_id: int, data: InfluenceIn, via: Via) -> Influence:
        deck = self._deck(deck_id)
        now = self.clock()
        row = data.model_dump() | self._resolve(deck, data)
        inf = Influence(
            **row, id=uuid.uuid4().hex[:12], deck_id=deck_id, via=via, created_at=now, updated_at=now
        )
        with self.store.tx() as db:
            db.execute(
                "INSERT INTO influences (id, deck_id, data) VALUES (?, ?, ?)",
                (inf.id, deck_id, inf.model_dump_json()),
            )
        return self.with_numbers(deck, inf)

    def get(self, deck_id: int, influence_id: str) -> Influence:
        with self.store.tx() as db:
            row = db.execute(
                "SELECT data FROM influences WHERE id = ? AND deck_id = ?", (influence_id, deck_id)
            ).fetchone()
        if row is None:
            raise FileError(404, f"no influence {influence_id} in deck {deck_id}")
        return self.with_numbers(self._deck(deck_id), Influence.model_validate_json(row["data"]))

    def update(self, deck_id: int, influence_id: str, patch: InfluencePatch) -> Influence:
        old = self.get(deck_id, influence_id)
        merged = InfluenceIn.model_validate(
            old.model_dump(include=set(InfluenceIn.model_fields)) | patch.model_dump(exclude_unset=True)
        )
        row = merged.model_dump() | self._resolve(self._deck(deck_id), merged)
        new = Influence.model_validate(old.model_dump() | row | {"updated_at": self.clock()})
        with self.store.tx() as db:
            db.execute(
                "INSERT INTO influence_history (influence_id, at, data) VALUES (?, ?, ?)",
                (influence_id, self.clock(), old.model_dump_json()),
            )
            db.execute("UPDATE influences SET data = ? WHERE id = ?", (new.model_dump_json(), influence_id))
        return self.with_numbers(self._deck(deck_id), new)

    def remove(self, deck_id: int, influence_id: str) -> None:
        old = self.get(deck_id, influence_id)
        with self.store.tx() as db:
            db.execute(
                "INSERT INTO influence_history (influence_id, at, data) VALUES (?, ?, ?)",
                (influence_id, self.clock(), old.model_dump_json()),
            )
            db.execute("DELETE FROM influences WHERE id = ?", (influence_id,))

    def history(self, influence_id: str) -> list[dict[str, Any]]:
        with self.store.tx() as db:
            rows = db.execute(
                "SELECT at, data FROM influence_history WHERE influence_id = ? ORDER BY rowid",
                (influence_id,),
            ).fetchall()
        return [{"at": r["at"], "data": json.loads(r["data"])} for r in rows]

    def list(
        self,
        deck_id: int,
        slide: int | None = None,
        kind: str | None = None,
        degree: str | None = None,
        author: str | None = None,
    ) -> list[Influence]:
        """The deck's influences, oldest first; ``slide`` keeps those that shape it (deck scope too)."""
        deck = self._deck(deck_id)
        with self.store.tx() as db:
            rows = db.execute(
                "SELECT data FROM influences WHERE deck_id = ? ORDER BY rowid", (deck_id,)
            ).fetchall()
        out = [self.with_numbers(deck, Influence.model_validate_json(r["data"])) for r in rows]
        return [
            i
            for i in out
            if (slide is None or i.scope.kind == "deck" or slide in i.scope.slides)
            and (kind is None or i.kind == kind)
            and (degree is None or i.degree == degree)
            and (author is None or author.lower() in (i.author.name.lower(), (i.author.tool or "").lower()))
        ]

    @staticmethod
    def with_numbers(deck: Deck, inf: Influence) -> Influence:
        """Today's slide numbers for the lasting ids (a slide that was removed drops out)."""
        numbers = [s.n for ref in inf.slide_ids if (s := deck.slide_by_ref(ref))]
        return inf.model_copy(update={"scope": inf.scope.model_copy(update={"slides": numbers})})

    def stale(self, inf: Influence) -> dict[str, tuple[int, int]]:
        """Files changed since the influence was written: file id → (then, now)."""
        out = {}
        for file_id, then in inf.versions.items():
            try:
                now = self.files.by_id(file_id).version
            except FileError:
                continue
            if now != then:
                out[file_id] = (then, now)
        return out
