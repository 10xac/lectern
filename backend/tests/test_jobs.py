"""AC-P1: asynchronous jobs, parallel researchers, SSE replay, cancellation and restarts."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Sequence

import pytest
from conftest import REPO
from fastapi.testclient import TestClient

from lectern.api import create_app
from lectern.graph.state import Block
from lectern.jobs import research
from lectern.jobs.manager import JobManager
from lectern.jobs.research import Context, Found, ToolCalls
from lectern.jobs.rows import JobRows
from lectern.models import Deck, SourceName, SourceReport
from lectern.providers.fake import FakeProvider
from lectern.store import Store


class SlowFake(FakeProvider):
    """The fake model, but every call takes ``delay`` seconds (in its worker thread)."""

    def __init__(self, delay: float) -> None:
        self.delay = delay

    def complete(self, system: str, blocks: Sequence[Block], question: str) -> str:
        time.sleep(self.delay)
        return super().complete(system, blocks, question)


def slow(
    source: SourceName, delay: float, log: list[tuple[str, float, float]]
) -> Callable[[Context, ToolCalls], Found]:
    def researcher(ctx: Context, calls: ToolCalls) -> Found:
        calls.take()
        start = time.perf_counter()
        time.sleep(delay)
        log.append((source, start, time.perf_counter()))
        return SourceReport(source=source, status="done", answer="x", r=0.5, g=0.5), []

    return researcher


def manager(store: Store, delay: float = 0.0) -> JobManager:
    return JobManager(store, SlowFake(delay) if delay else FakeProvider())


def seed_memory(jobs: JobManager, deck: Deck, question: str = "Why did the harbour cafe grow?") -> None:
    """Answer one question first, so triage sends a similar one to memory (M) too."""

    async def go() -> None:
        await jobs.wait(jobs.submit(deck, 2, question).id)

    asyncio.run(go())


def test_three_jobs_on_three_slides_overlap_and_land_on_their_own_slide(store: Store, kettle: Deck) -> None:
    jobs = manager(store, delay=0.15)

    async def go() -> list[str]:
        started = [jobs.submit(kettle, n, f"What does slide {n} say about revenue?") for n in (1, 2, 3)]
        await asyncio.gather(*(jobs.wait(j.id) for j in started))
        return [j.id for j in started]

    ids = asyncio.run(go())
    spans = []
    for n, job_id in zip((1, 2, 3), ids, strict=True):
        events = jobs.rows.events(job_id)
        spans.append((events[0].data["t"], events[-1].data["t"]))
        job = jobs.rows.get(job_id)
        assert job is not None and job.status == "answered" and job.slide == n
        thread = jobs.rows.messages(kettle.id or 0, n)
        assert [(m.role, m.job_id) for m in thread] == [("user", job_id), ("agent", job_id)]
    assert max(s for s, _ in spans) < min(e for _, e in spans)  # all three were running at once


def test_researchers_of_one_job_run_concurrently(
    store: Store, kettle: Deck, monkeypatch: pytest.MonkeyPatch
) -> None:
    log: list[tuple[str, float, float]] = []
    jobs = manager(store)
    seed_memory(jobs, kettle)
    monkeypatch.setitem(research.RESEARCHERS, "K", slow("K", 0.2, log))
    monkeypatch.setitem(research.RESEARCHERS, "M", slow("M", 0.2, log))

    async def go() -> None:
        await jobs.wait(jobs.submit(kettle, 2, "Why did the harbour cafe grow?").id)

    asyncio.run(go())
    (_, s1, e1), (_, s2, e2) = sorted(log)
    assert max(s1, s2) < min(e1, e2)


def test_budget_time_limit_answers_from_what_was_found(
    store: Store, kettle: Deck, monkeypatch: pytest.MonkeyPatch
) -> None:
    jobs = manager(store)
    seed_memory(jobs, kettle)
    monkeypatch.setitem(research.RESEARCHERS, "M", slow("M", 0.5, []))
    store.set_agent(kettle.id or 0, None, {"budget": {"max_seconds": 0.1}})
    deck = store.get_deck(kettle.id or 0)
    assert deck is not None

    async def go() -> str:
        job = jobs.submit(deck, 2, "Why did the harbour cafe grow?")
        await jobs.wait(job.id)
        return job.id

    job = jobs.rows.get(asyncio.run(go()))
    assert job is not None and job.status == "answered" and job.answer is not None
    assert any("ran out of time" in n for n in job.notes)
    assert {s.source: s.status for s in job.sources}["M"] == "timeout"
    assert {s.source: s.status for s in job.sources}["K"] == "done"


def test_cancel_stops_the_researchers(store: Store, kettle: Deck, monkeypatch: pytest.MonkeyPatch) -> None:
    log: list[tuple[str, float, float]] = []
    monkeypatch.setitem(research.RESEARCHERS, "K", slow("K", 0.3, log))
    monkeypatch.setitem(research.RESEARCHERS, "M", slow("M", 0.3, log))
    jobs = manager(store)

    async def go() -> str:
        job = jobs.submit(kettle, 1, "anything")
        await asyncio.sleep(0.05)
        assert jobs.cancel(job.id)
        await jobs.wait(job.id)
        assert not jobs.cancel(job.id)  # already over
        return job.id

    job_id = asyncio.run(go())
    job = jobs.rows.get(job_id)
    assert job is not None and job.status == "cancelled"
    finished = [
        e for e in jobs.rows.events(job_id) if e.kind == "researcher" and e.data["state"] != "running"
    ]
    assert finished == []  # no researcher reported back after the cancel
    assert [m.role for m in jobs.rows.messages(kettle.id or 0, 1)] == ["user"]


def test_a_restart_marks_running_jobs_interrupted(tmp_path: pytest.TempPathFactory) -> None:
    path = f"{tmp_path}/jobs.db"
    rows = JobRows(Store(path))
    running = rows.create(1, 1, "q")
    rows.set_status(running.id, "researching")
    done = rows.create(1, 2, "q")
    rows.finish(done.id, "answered", None, [], [])
    with TestClient(create_app(Store(path), FakeProvider())) as client:  # the lifespan runs recover()
        assert client.get(f"/jobs/{running.id}").json()["error"] == "interrupted"
        assert client.get(f"/jobs/{running.id}").json()["status"] == "failed"
        assert client.get(f"/jobs/{done.id}").json()["status"] == "answered"
        assert client.get("/jobs/nope").status_code == 404


def sse(text: str) -> list[dict[str, str]]:
    out = []
    for chunk in text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in chunk.splitlines())
        out.append(fields)
    return out


def test_api_jobs_sse_replay_threads_and_deck_questions() -> None:
    with TestClient(create_app(Store(), FakeProvider())) as client:
        pptx = (REPO / "decks" / "kettle-quarterly-review.pptx").read_bytes()
        d = client.post("/decks", files={"file": ("k.pptx", pptx)}).json()["id"]
        queued = client.post(f"/decks/{d}/slides/2/ask", json={"question": "Why did the harbour cafe grow?"})
        assert queued.status_code == 202 and queued.json()["status"] == "queued"
        job_id = queued.json()["id"]
        everything = sse(client.get(f"/jobs/{job_id}/events").text)
        assert everything[0]["id"] == "1" and everything[-1]["event"] == "done"
        kinds = [e["event"] for e in everything]
        assert {"status", "triage", "researcher", "done"} <= set(kinds)
        replay = sse(client.get(f"/jobs/{job_id}/events", headers={"Last-Event-ID": "3"}).text)
        assert replay[0]["id"] == "4" and replay == everything[3:]
        thread = client.get(f"/decks/{d}/slides/2/messages").json()
        assert [m["role"] for m in thread] == ["user", "agent"] and thread[1]["answer"]["agent"] == "slide-2"
        deck_job = client.post(f"/decks/{d}/ask?wait=true", json={"question": "Summarise the deck"}).json()
        assert deck_job["answer"]["agent"] == "deck" and deck_job["slide"] is None
        assert [m["role"] for m in client.get(f"/decks/{d}/messages").json()] == ["user", "agent"]
        assert client.get(f"/decks/{d}/slides/2/messages").json() == thread  # the deck's thread is separate
        assert client.delete(f"/jobs/{job_id}").json()["status"] == "answered"  # nothing left to cancel
        bad = client.post(f"/decks/{d}/ask", json={"question": "q", "agent": {"tools": ["web_search"]}})
        assert bad.status_code == 422
