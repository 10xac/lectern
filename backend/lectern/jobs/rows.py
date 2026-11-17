"""Job, job-event and thread rows in the same SQLite file as everything else.

A job is a row; its progress is an append-only list of events (the SSE stream replays them from
``Last-Event-ID``); each answer is also posted to its slide's thread (``slide_messages``).
"""

from __future__ import annotations

import json
import uuid

from lectern.models import TERMINAL, Answer, Job, JobEvent, JobStatus, Message, SourceReport
from lectern.store import Store

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY, deck_id INTEGER NOT NULL, slide INTEGER, question TEXT NOT NULL,
  status TEXT NOT NULL, result TEXT, error TEXT, feedback INTEGER, viewer TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS job_events (
  job_id TEXT NOT NULL, seq INTEGER NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL,
  PRIMARY KEY (job_id, seq));
CREATE TABLE IF NOT EXISTS slide_messages (
  id INTEGER PRIMARY KEY, deck_id INTEGER NOT NULL, slide INTEGER, role TEXT NOT NULL,
  text TEXT NOT NULL, job_id TEXT, answer TEXT, viewer TEXT NOT NULL DEFAULT '');
"""
# Added after the first v0.2 databases were made: each viewer has their own threads (decision D14).
ADDED = [("jobs", "viewer"), ("slide_messages", "viewer")]
JOB_COLUMNS = ("id", "deck_id", "slide", "question", "status", "error", "feedback", "viewer")
MESSAGE_COLUMNS = ("id", "deck_id", "slide", "role", "text", "job_id")
RUNNING = tuple(s for s in JobStatus.__args__ if s not in TERMINAL)  # type: ignore[attr-defined]


class JobRows:
    """The job tables, sharing the store's connection and lock."""

    def __init__(self, store: Store) -> None:
        self.store = store
        with store.tx() as db:
            db.executescript(SCHEMA)
            for table, column in ADDED:
                if column not in {c["name"] for c in db.execute(f"PRAGMA table_info({table})")}:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")

    def create(self, deck_id: int, slide: int | None, question: str, viewer: str = "") -> Job:
        job = Job(id=uuid.uuid4().hex[:12], deck_id=deck_id, slide=slide, question=question, viewer=viewer)
        with self.store.tx() as db:
            db.execute(
                "INSERT INTO jobs (id, deck_id, slide, question, status, viewer) VALUES (?, ?, ?, ?, ?, ?)",
                (job.id, deck_id, slide, question, job.status, viewer),
            )
        return job

    def get(self, job_id: str) -> Job | None:
        with self.store.tx() as db:
            row = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        extra = json.loads(row["result"]) if row["result"] else {}
        return Job(**{k: row[k] for k in JOB_COLUMNS}, **extra)

    def set_status(self, job_id: str, status: JobStatus, error: str | None = None) -> None:
        with self.store.tx() as db:
            db.execute("UPDATE jobs SET status = ?, error = ? WHERE id = ?", (status, error, job_id))

    def finish(
        self,
        job_id: str,
        status: JobStatus,
        answer: Answer | None,
        sources: list[SourceReport],
        notes: list[str],
    ) -> None:
        result = {
            "answer": answer.model_dump() if answer else None,
            "sources": [s.model_dump() for s in sources],
            "notes": notes,
        }
        with self.store.tx() as db:
            db.execute(
                "UPDATE jobs SET status = ?, result = ? WHERE id = ?", (status, json.dumps(result), job_id)
            )

    def set_feedback(self, job_id: str, vote: int) -> None:
        with self.store.tx() as db:
            db.execute("UPDATE jobs SET feedback = ? WHERE id = ?", (vote, job_id))

    def mark_interrupted(self) -> int:
        """After a restart nothing is running any more: those jobs failed."""
        marks = ",".join("?" * len(RUNNING))
        with self.store.tx() as db:
            cur = db.execute(
                f"UPDATE jobs SET status = 'failed', error = 'interrupted' WHERE status IN ({marks})", RUNNING
            )
        return cur.rowcount

    def all(self) -> list[Job]:
        """Every job, oldest first (the ``/jobs.jsonl`` export)."""
        with self.store.tx() as db:
            ids = [r["id"] for r in db.execute("SELECT id FROM jobs ORDER BY rowid")]
        return [job for i in ids if (job := self.get(i)) is not None]

    def answered(self, deck_id: int) -> list[Job]:
        """The deck's answered jobs, oldest first: lectern's memory (source M)."""
        with self.store.tx() as db:
            ids = [
                r["id"]
                for r in db.execute(
                    "SELECT id FROM jobs WHERE deck_id = ? AND status = 'answered' ORDER BY rowid", (deck_id,)
                )
            ]
        return [job for i in ids if (job := self.get(i)) is not None]

    # events ---------------------------------------------------------------------------------

    def add_event(self, job_id: str, kind: str, data: dict[str, object]) -> JobEvent:
        with self.store.tx() as db:
            row = db.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM job_events WHERE job_id = ?", (job_id,))
            seq = int(row.fetchone()[0])
            db.execute(
                "INSERT INTO job_events (job_id, seq, kind, data) VALUES (?, ?, ?, ?)",
                (job_id, seq, kind, json.dumps(data)),
            )
        return JobEvent(seq=seq, kind=kind, data=data)

    def events(self, job_id: str, after: int = 0) -> list[JobEvent]:
        with self.store.tx() as db:
            rows = db.execute(
                "SELECT * FROM job_events WHERE job_id = ? AND seq > ? ORDER BY seq", (job_id, after)
            ).fetchall()
        return [JobEvent(seq=r["seq"], kind=r["kind"], data=json.loads(r["data"])) for r in rows]

    # threads --------------------------------------------------------------------------------

    def add_message(
        self,
        deck_id: int,
        slide: int | None,
        role: str,
        text: str,
        job_id: str | None,
        answer: Answer | None = None,
        viewer: str = "",
    ) -> None:
        with self.store.tx() as db:
            db.execute(
                "INSERT INTO slide_messages (deck_id, slide, role, text, job_id, answer, viewer)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (deck_id, slide, role, text, job_id, answer.model_dump_json() if answer else None, viewer),
            )

    def messages(self, deck_id: int, slide: int | None, viewer: str = "") -> list[Message]:
        """One viewer's thread on a slide (``slide=None``: on the deck), oldest first."""
        with self.store.tx() as db:
            rows = db.execute(
                "SELECT * FROM slide_messages WHERE deck_id = ? AND slide IS ? AND viewer = ? ORDER BY id",
                (deck_id, slide, viewer),
            ).fetchall()
        return [
            Message(
                **{k: r[k] for k in MESSAGE_COLUMNS},
                answer=Answer.model_validate_json(r["answer"]) if r["answer"] else None,
            )
            for r in rows
        ]
