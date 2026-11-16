"""SQLite storage (stdlib ``sqlite3``): decks, slides, attachments, chunks and traces.

One connection, guarded by a lock, because FastAPI runs plain ``def`` routes on a thread pool.
Every read that touches deck content takes a ``deck_id``: a single local user still keeps each
deck's data to itself.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from lectern.models import Attachment, Chunk, Deck, Slide, Trace, TraceStep

SCHEMA = """
CREATE TABLE IF NOT EXISTS decks (
  id INTEGER PRIMARY KEY, title TEXT NOT NULL, source TEXT NOT NULL,
  persona TEXT, outline TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS slides (
  deck_id INTEGER NOT NULL REFERENCES decks(id), n INTEGER NOT NULL,
  title TEXT NOT NULL, body TEXT NOT NULL, notes TEXT NOT NULL, html TEXT, persona TEXT,
  PRIMARY KEY (deck_id, n));
CREATE TABLE IF NOT EXISTS attachments (
  id INTEGER PRIMARY KEY, deck_id INTEGER NOT NULL REFERENCES decks(id), name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chunks (
  attachment_id INTEGER NOT NULL REFERENCES attachments(id), deck_id INTEGER NOT NULL,
  idx INTEGER NOT NULL, text TEXT NOT NULL, PRIMARY KEY (attachment_id, idx));
CREATE TABLE IF NOT EXISTS traces (
  id INTEGER PRIMARY KEY, deck_id INTEGER, template TEXT NOT NULL, agent TEXT NOT NULL,
  outcome TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS trace_steps (
  trace_id INTEGER NOT NULL REFERENCES traces(id), idx INTEGER NOT NULL, node TEXT NOT NULL,
  outcome TEXT NOT NULL, block_ids TEXT NOT NULL, ms REAL, PRIMARY KEY (trace_id, idx));
"""
# Columns added after v0.1: (table, column, type). ``_migrate`` adds the missing ones, so an
# existing lectern.db keeps working.
ADDED_COLUMNS = [
    ("decks", "agent", "TEXT"),
    ("slides", "agent", "TEXT"),
    ("decks", "file_id", "TEXT"),
    ("decks", "folder", "TEXT"),
    ("slides", "file_id", "TEXT"),
]


def dumps(value: object) -> str | None:
    return None if value is None else json.dumps(value)


def loads(value: str | None) -> Any:
    return None if value is None else json.loads(value)


class Store:
    """The only place that speaks SQL."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self.tx() as db:
            db.executescript(SCHEMA)
            self._migrate(db)

    @staticmethod
    def _migrate(db: sqlite3.Connection) -> None:
        for table, column, kind in ADDED_COLUMNS:
            have = {r["name"] for r in db.execute(f"PRAGMA table_info({table})")}
            if column not in have:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock, self._db:
            yield self._db

    # decks ---------------------------------------------------------------------------------

    def add_deck(self, deck: Deck) -> int:
        """Save a deck and its slides; returns the new deck id."""
        with self.tx() as db:
            cur = db.execute(
                "INSERT INTO decks (title, source, persona, outline, agent, file_id, folder)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    deck.title,
                    deck.source,
                    deck.persona,
                    deck.outline,
                    dumps(deck.agent),
                    deck.file_id,
                    deck.folder,
                ),
            )
            deck_id = int(cur.lastrowid or 0)
            self._insert_slides(db, deck_id, deck.slides)
        return deck_id

    @staticmethod
    def _insert_slides(db: sqlite3.Connection, deck_id: int, slides: Sequence[Slide]) -> None:
        db.executemany(
            "INSERT INTO slides (deck_id, n, title, body, notes, html, persona, agent, file_id)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (deck_id, s.n, s.title, s.body, s.notes, s.html, s.persona, dumps(s.agent), s.file_id)
                for s in slides
            ],
        )

    def replace_slides(self, deck_id: int, slides: Sequence[Slide], outline: str) -> None:
        """A folder deck's slides, rebuilt from its files after any change."""
        with self.tx() as db:
            db.execute("DELETE FROM slides WHERE deck_id = ?", (deck_id,))
            self._insert_slides(db, deck_id, slides)
            db.execute("UPDATE decks SET outline = ? WHERE id = ?", (outline, deck_id))

    def set_deck_file(self, deck_id: int, file_id: str) -> None:
        with self.tx() as db:
            db.execute("UPDATE decks SET file_id = ? WHERE id = ?", (file_id, deck_id))

    def deck_by_folder(self, folder: str) -> int | None:
        with self.tx() as db:
            row = db.execute("SELECT id FROM decks WHERE folder = ?", (folder,)).fetchone()
        return None if row is None else int(row["id"])

    def get_deck(self, deck_id: int) -> Deck | None:
        """The deck with its slides in order, or ``None``."""
        with self.tx() as db:
            row = db.execute("SELECT * FROM decks WHERE id = ?", (deck_id,)).fetchone()
            if row is None:
                return None
            slides = db.execute("SELECT * FROM slides WHERE deck_id = ? ORDER BY n", (deck_id,)).fetchall()
        return Deck(
            id=row["id"],
            title=row["title"],
            source=row["source"],
            persona=row["persona"],
            agent=loads(row["agent"]),
            file_id=row["file_id"],
            folder=row["folder"],
            outline=row["outline"],
            slides=[
                Slide(
                    n=s["n"],
                    title=s["title"],
                    body=s["body"],
                    notes=s["notes"],
                    html=s["html"],
                    persona=s["persona"],
                    agent=loads(s["agent"]),
                    file_id=s["file_id"],
                )
                for s in slides
            ],
        )

    def set_agent(self, deck_id: int, n: int | None, agent: dict[str, Any] | None) -> None:
        """Replace the deck's (``n=None``) or one slide's agent layer."""
        with self.tx() as db:
            if n is None:
                db.execute("UPDATE decks SET agent = ? WHERE id = ?", (dumps(agent), deck_id))
            else:
                db.execute(
                    "UPDATE slides SET agent = ? WHERE deck_id = ? AND n = ?", (dumps(agent), deck_id, n)
                )

    def list_decks(self) -> list[Deck]:
        """Every deck, newest first, without slides (the deck list does not need them)."""
        with self.tx() as db:
            rows = db.execute("SELECT * FROM decks ORDER BY id DESC").fetchall()
        return [Deck(id=r["id"], title=r["title"], source=r["source"], outline=r["outline"]) for r in rows]

    # attachments ---------------------------------------------------------------------------

    def add_attachment(self, deck_id: int, name: str, chunks: Sequence[str]) -> Attachment:
        """Save an attachment and its chunks for one deck."""
        with self.tx() as db:
            cur = db.execute("INSERT INTO attachments (deck_id, name) VALUES (?, ?)", (deck_id, name))
            att_id = int(cur.lastrowid or 0)
            db.executemany(
                "INSERT INTO chunks (attachment_id, deck_id, idx, text) VALUES (?, ?, ?, ?)",
                [(att_id, deck_id, i, text) for i, text in enumerate(chunks)],
            )
        return Attachment(id=att_id, deck_id=deck_id, name=name, chunks=len(chunks))

    def attachments(self, deck_id: int) -> list[Attachment]:
        """The deck's attachments in upload order."""
        with self.tx() as db:
            rows = db.execute(
                "SELECT a.id, a.deck_id, a.name, COUNT(c.idx) AS n FROM attachments a"
                " LEFT JOIN chunks c ON c.attachment_id = a.id WHERE a.deck_id = ?"
                " GROUP BY a.id ORDER BY a.id",
                (deck_id,),
            ).fetchall()
        return [Attachment(id=r["id"], deck_id=r["deck_id"], name=r["name"], chunks=r["n"]) for r in rows]

    def chunks(self, deck_id: int) -> list[Chunk]:
        """Every attachment chunk that belongs to ``deck_id``, in a stable order."""
        with self.tx() as db:
            rows = db.execute(
                "SELECT * FROM chunks WHERE deck_id = ? ORDER BY attachment_id, idx", (deck_id,)
            ).fetchall()
        return [
            Chunk(attachment_id=r["attachment_id"], deck_id=r["deck_id"], index=r["idx"], text=r["text"])
            for r in rows
        ]

    # traces --------------------------------------------------------------------------------

    def add_trace(
        self, deck_id: int | None, template: str, agent: str, outcome: str, steps: Sequence[TraceStep]
    ) -> int:
        """Save one graph run; returns the trace id."""
        with self.tx() as db:
            cur = db.execute(
                "INSERT INTO traces (deck_id, template, agent, outcome) VALUES (?, ?, ?, ?)",
                (deck_id, template, agent, outcome),
            )
            trace_id = int(cur.lastrowid or 0)
            db.executemany(
                "INSERT INTO trace_steps (trace_id, idx, node, outcome, block_ids, ms)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                [(trace_id, s.index, s.node, s.outcome, json.dumps(s.block_ids), s.ms) for s in steps],
            )
        return trace_id

    def get_trace(self, trace_id: int) -> Trace | None:
        """A stored trace with its steps, or ``None``."""
        with self.tx() as db:
            row = db.execute("SELECT * FROM traces WHERE id = ?", (trace_id,)).fetchone()
            if row is None:
                return None
            steps = db.execute(
                "SELECT * FROM trace_steps WHERE trace_id = ? ORDER BY idx", (trace_id,)
            ).fetchall()
        return Trace(
            id=row["id"],
            deck_id=row["deck_id"],
            template=row["template"],
            agent=row["agent"],
            outcome=row["outcome"],
            steps=[
                TraceStep(
                    index=s["idx"],
                    node=s["node"],
                    outcome=s["outcome"],
                    block_ids=json.loads(s["block_ids"]),
                    ms=s["ms"],
                )
                for s in steps
            ],
        )
