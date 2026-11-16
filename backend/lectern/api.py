"""The HTTP API (FastAPI).

    POST /decks                          upload a deck (multipart ``file``) → the deck
    GET  /decks                          the deck list
    GET  /decks/{id}                     one deck with its slides and attachments
    POST /decks/{id}/attachments         upload author data (multipart ``file``)
    POST /decks/{id}/slides/{n}/ask      {question, agent?} → 202 job (see ``jobs/routes.py``)
    GET  /traces/{id}                    one graph run, step by step
    GET  /agents/resolve?deck=&slide=    the effective AgentSpec, each field's layer, key set/unset
    PUT  /decks/{id}/agent               the deck's AgentSpec layer (JSON object, or null)
    PUT  /decks/{id}/slides/{n}/agent    one slide's AgentSpec layer

An ask also takes ``agent``, the request's override (persona, an allow-listed model, fewer tools,
a lower budget). A refused override or layer is a 422.

Uploads are capped at 20 MB per file; decks at 200 slides (the ``normalise`` node).
"""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Body, FastAPI, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from lectern import guard, mcp_server, service
from lectern.agents import resolve
from lectern.auth_routes import add_auth_routes
from lectern.blobs import BlobStore, MemoryBlobs, blobs_from_env
from lectern.dna import DNA
from lectern.dna.routes import add_dna_routes
from lectern.files import Files
from lectern.http import Http
from lectern.hub import Hub
from lectern.jobs.manager import JobManager
from lectern.jobs.routes import add_job_routes
from lectern.jobs.system1 import resolve_system1
from lectern.models import Attachment, Deck, Trace
from lectern.providers.base import Provider, get_provider, provider_for
from lectern.settings import Settings
from lectern.store import Store
from lectern.users import Users

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


class DeckOut(Deck):
    """A deck as the API returns it: with its attachments."""

    attachments: list[Attachment] = Field(default_factory=list)


class DeckSummary(BaseModel):
    id: int
    title: str
    source: str


AgentLayer = Annotated[dict[str, Any] | None, Body()]


def read_upload(file: UploadFile) -> bytes:
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"files are limited to {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    return data


def build_hub(
    store: Store | None = None,
    provider: Provider | None = None,
    clock: Callable[[], float] | None = None,
    providers: service.ProviderFactory | None = None,
    blobs: BlobStore | None = None,
    http: Http | None = None,
) -> Hub:
    """Wire the store, registry, DNA and job manager. The API, ``lectern mcp`` and the CLI share it.

    ``providers`` builds one provider per agent instance; by default each instance's model binding
    is honoured, unless the caller passed a single ``provider`` (tests), which then answers for all.
    Blobs default to ``LECTERN_BLOBS``, or to memory when the caller passed its own store (tests).
    """
    db = store or Store(os.environ.get("LECTERN_DB", "lectern.db"))
    settings = Settings(db)  # applies what admins stored before any provider is built
    model = provider or get_provider()
    per_instance = providers or (None if provider else provider_for)
    files = Files(db, blobs or (MemoryBlobs() if store else blobs_from_env()))
    dna = DNA(db, files)
    jobs = JobManager(db, model, per_instance, clock=clock or time.perf_counter, http=http, dna=dna)
    return Hub(db, files, dna, jobs, Users(db), settings)


def create_app(*args: Any, **kwargs: Any) -> FastAPI:
    """Build the app; the arguments are ``build_hub``'s. Tests pass an in-memory store, the fake
    provider and a fake clock."""
    hub = build_hub(*args, **kwargs)
    db, jobs = hub.store, hub.jobs
    mcp = mcp_server.build(hub)
    mcp_app = mcp.streamable_http_app(streamable_http_path="/", transport_security=guard.mcp_hosts())

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        jobs.recover()  # jobs a previous process was running are failed: interrupted
        async with mcp.session_manager.run():
            yield

    app = FastAPI(title="lectern", version="0.2.1", lifespan=lifespan)
    app.state.hub = hub
    guard.install(app, hub.users)
    add_auth_routes(app, hub.users, hub.settings, guard.auth_on(os.environ))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": app.version}

    app.mount("/mcp", mcp_app)

    @app.post("/decks", status_code=201)
    def upload_deck(file: UploadFile) -> DeckOut:
        deck = hub.create_deck(file.filename or "deck", read_upload(file))
        return DeckOut(**deck.model_dump())

    @app.get("/decks")
    def list_decks() -> list[DeckSummary]:
        return [DeckSummary(id=d.id or 0, title=d.title, source=d.source) for d in db.list_decks()]

    @app.get("/decks/{deck_id}")
    def get_deck(deck_id: int) -> DeckOut:
        return DeckOut(**hub.deck(deck_id).model_dump(), attachments=db.attachments(deck_id))

    @app.post("/decks/{deck_id}/attachments", status_code=201)
    def add_attachment(deck_id: int, file: UploadFile) -> Attachment:
        hub.deck(deck_id)
        return service.attach(db, deck_id, file.filename or "data.txt", read_upload(file))

    @app.get("/traces/{trace_id}")
    def get_trace(trace_id: int) -> Trace:
        trace = db.get_trace(trace_id)
        if trace is None:
            raise HTTPException(404, f"no trace {trace_id}")
        return trace

    add_agent_routes(app, hub)
    add_job_routes(app, jobs, hub.deck)
    add_dna_routes(app, hub, read_upload)
    static = os.environ.get("LECTERN_STATIC")  # the built web app, served by the same process
    if static and Path(static).is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="web")
    return app


def add_agent_routes(app: FastAPI, hub: Hub) -> None:
    """``/agents/resolve`` and the deck and slide agent layers."""

    @app.get("/agents/resolve")
    def resolve_agent(deck: int, slide: int | None = None) -> dict[str, Any]:
        loaded = hub.deck(deck, slide)
        return resolve(loaded, slide).public() | {"system1": resolve_system1(os.environ).public(os.environ)}

    @app.put("/decks/{deck_id}/agent")
    def put_deck_agent(deck_id: int, agent: AgentLayer = None) -> dict[str, Any]:
        deck = hub.deck(deck_id)
        return resolve(service.set_agent(hub.store, deck, None, agent), None).public()

    @app.put("/decks/{deck_id}/slides/{n}/agent")
    def put_slide_agent(deck_id: int, n: int, agent: AgentLayer = None) -> dict[str, Any]:
        deck = hub.deck(deck_id, n)
        return resolve(service.set_agent(hub.store, deck, n, agent), n).public()
