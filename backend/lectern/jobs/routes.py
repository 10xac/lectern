"""Job routes: ask (202 + a job), progress over SSE, cancel, and each slide's thread.

POST   /decks/{d}/slides/{n}/ask   {question, agent?} → 202 Job   (?wait=true: the finished job)
POST   /decks/{d}/ask              the same, for the deck agent
GET    /jobs/{id}                  status, answer, per-source reports
GET    /jobs/{id}/events           SSE; replays from Last-Event-ID
DELETE /jobs/{id}                  cancel
POST   /jobs/{id}/feedback         {vote: up|down} on the answer (memory's track record)
GET    /jobs.jsonl                 one line per job: triage features, route, verdict, outcome
GET    /decks/{d}/slides/{n}/messages, /decks/{d}/messages   a slide's / the deck's thread
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from lectern.agents.spec import RequestAgent
from lectern.jobs.manager import JobManager
from lectern.models import Deck, Job, Message


class Feedback(BaseModel):
    vote: Literal["up", "down"]


def export_line(job: Job) -> dict[str, Any]:
    """What a later, learned triage can be trained on: features, decisions and how it went."""
    conf = (job.answer.confidence if job.answer else None) or {}
    fusion = conf.get("fusion") or {}
    own = job.model_dump(include={"id", "deck_id", "slide", "question", "status", "feedback"})
    picked = {k: conf.get(k) for k in ("triage", "sources", "verdict")}
    return own | picked | {k: fusion.get(k) for k in ("p_best", "kappa", "z")}


class AskBody(BaseModel):
    """A question plus the request's agent override. History comes from the slide's thread."""

    question: str
    agent: RequestAgent | None = None


def add_job_routes(app: FastAPI, jobs: JobManager, load: Callable[[int, int | None], Deck]) -> None:
    async def start(deck_id: int, n: int | None, body: AskBody, wait: bool) -> Job:
        job = jobs.submit(load(deck_id, n), n, body.question.strip(), body.agent)
        return (await jobs.wait(job.id) or job) if wait else job

    @app.post("/decks/{deck_id}/slides/{n}/ask", status_code=202)
    async def ask_slide(deck_id: int, n: int, body: AskBody, wait: bool = False) -> Job:
        return await start(deck_id, n, body, wait)

    @app.post("/decks/{deck_id}/ask", status_code=202)
    async def ask_deck(deck_id: int, body: AskBody, wait: bool = False) -> Job:
        return await start(deck_id, None, body, wait)

    def get(job_id: str) -> Job:
        job = jobs.rows.get(job_id)
        if job is None:
            raise HTTPException(404, f"no job {job_id}")
        return job

    @app.get("/jobs.jsonl")
    def export_jobs() -> PlainTextResponse:
        lines = (json.dumps(export_line(job)) for job in jobs.rows.all())
        return PlainTextResponse("".join(f"{line}\n" for line in lines), media_type="application/jsonl")

    @app.post("/jobs/{job_id}/feedback")
    def feedback(job_id: str, body: Feedback) -> Job:
        get(job_id)
        jobs.rows.set_feedback(job_id, 1 if body.vote == "up" else -1)
        return get(job_id)

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str) -> Job:
        return get(job_id)

    @app.delete("/jobs/{job_id}")
    async def cancel_job(job_id: str) -> Job:
        get(job_id)
        if jobs.cancel(job_id):
            await jobs.wait(job_id)
        return get(job_id)

    @app.get("/jobs/{job_id}/events")
    def job_events(job_id: str, last_event_id: int = Header(0)) -> StreamingResponse:
        get(job_id)

        async def sse() -> AsyncIterator[str]:
            async for event in jobs.stream(job_id, last_event_id):
                yield f"id: {event.seq}\nevent: {event.kind}\ndata: {json.dumps(event.data)}\n\n"

        return StreamingResponse(sse(), media_type="text/event-stream")

    @app.get("/decks/{deck_id}/slides/{n}/messages")
    def slide_messages(deck_id: int, n: int) -> list[Message]:
        load(deck_id, n)
        return jobs.rows.messages(deck_id, n)

    @app.get("/decks/{deck_id}/messages")
    def deck_messages(deck_id: int) -> list[Message]:
        load(deck_id, None)
        return jobs.rows.messages(deck_id, None)
