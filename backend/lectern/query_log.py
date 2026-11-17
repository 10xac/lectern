"""Query logging for evaluation: every answered question records its retrieval signals."""

from __future__ import annotations

import json
from collections.abc import Sequence

from lectern.models import QueryLogEntry
from lectern.store import Store


class QueryLog:
    def __init__(self, store: Store) -> None:
        self._store = store

    def log(
        self, deck_id: int, slide: int | None, question: str, agent: str, outcome: str,
        answer: str, citations: Sequence[str], block_ids: Sequence[str],
        bm25_scores: dict[str, float], trace_id: int | None, ms: float | None,
    ) -> int:
        with self._store.tx() as db:
            cur = db.execute(
                "INSERT INTO query_log"
                " (deck_id, slide, question, agent, outcome, answer, citations, block_ids,"
                "  bm25_scores, trace_id, ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (deck_id, slide, question, agent, outcome, answer,
                 json.dumps(list(citations)), json.dumps(list(block_ids)),
                 json.dumps(bm25_scores), trace_id, ms),
            )
        return int(cur.lastrowid or 0)

    def entries(self, deck_id: int | None = None, limit: int = 200) -> list[QueryLogEntry]:
        with self._store.tx() as db:
            if deck_id is not None:
                rows = db.execute(
                    "SELECT * FROM query_log WHERE deck_id = ? ORDER BY id DESC LIMIT ?", (deck_id, limit)
                ).fetchall()
            else:
                rows = db.execute("SELECT * FROM query_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [
            QueryLogEntry(
                id=r["id"], deck_id=r["deck_id"], slide=r["slide"], question=r["question"],
                agent=r["agent"], outcome=r["outcome"], answer=r["answer"],
                citations=json.loads(r["citations"]), block_ids=json.loads(r["block_ids"]),
                bm25_scores=json.loads(r["bm25_scores"]), trace_id=r["trace_id"],
                ms=r["ms"], created=r["created"],
            )
            for r in rows
        ]
