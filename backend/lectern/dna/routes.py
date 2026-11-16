"""REST for the DNA, the file registry and folder decks. Thin: each route calls ``Hub``.

POST/GET          /decks/{d}/influences          (GET filters: slide, kind, degree, author)
PATCH/DELETE      /decks/{d}/influences/{id}     GET …/{id}/history
POST              /decks/{d}/influences/batch    a list, all or nothing
POST              /decks/{d}/files               upload a reference (multipart ``file``)
GET               /decks/{d}/dna, /decks/{d}/slides/{n}/dna   ?format=graph|text
PUT/GET           /slides?path=                  a slide file's body (PUT: ?mode=create|overwrite|upsert)
GET               /files?prefix=&deck=           the registry
GET/DELETE        /file?path=                    one file (DELETE ?purge=true forgets it)
GET/PUT           /file/content?path=            its bytes
PATCH             /file/meta?path=               merge metadata (title, notes, order, persona, agent …)
POST              /file/move                     {src, dst}
POST              /files/reconcile               find missing and unregistered files
POST/DELETE       /files/{id}/relink, /files/{id}   relink a missing file, or delete its metadata
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import Body, FastAPI, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from lectern.agents.spec import SpecError
from lectern.dna import Influence, InfluenceIn, InfluencePatch
from lectern.files import FileError, Mode, Reconciled, StoredFile
from lectern.hub import Hub
from lectern.models import IngestError

RestVia = Literal["api", "ui", "cli"]  # the web app says ui; MCP records mcp itself


class Move(BaseModel):
    src: str
    dst: str


class Relink(BaseModel):
    path: str


def add_dna_routes(app: FastAPI, hub: Hub, read_upload: Any) -> None:
    @app.exception_handler(FileError)
    async def file_error(_: Request, exc: FileError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=exc.status)

    @app.exception_handler(IngestError)
    @app.exception_handler(SpecError)
    async def refused(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.post("/decks/{deck_id}/influences", status_code=201)
    def add_influence(deck_id: int, body: InfluenceIn, via: RestVia = "api") -> Influence:
        return hub.add_influence(deck_id, body, via)

    @app.post("/decks/{deck_id}/influences/batch", status_code=201)
    def add_influences(deck_id: int, body: list[InfluenceIn], via: RestVia = "api") -> list[Influence]:
        return hub.add_influences(deck_id, body, via)

    @app.get("/decks/{deck_id}/influences")
    def list_influences(
        deck_id: int,
        slide: int | None = None,
        kind: str | None = None,
        degree: str | None = None,
        author: str | None = None,
    ) -> list[Influence]:
        hub.deck(deck_id)
        return hub.dna.list(deck_id, slide, kind, degree, author)

    @app.patch("/decks/{deck_id}/influences/{influence_id}")
    def update_influence(deck_id: int, influence_id: str, body: InfluencePatch) -> Influence:
        return hub.update_influence(deck_id, influence_id, body)

    @app.delete("/decks/{deck_id}/influences/{influence_id}", status_code=204)
    def remove_influence(deck_id: int, influence_id: str) -> None:
        hub.dna.remove(deck_id, influence_id)

    @app.get("/decks/{deck_id}/influences/{influence_id}/history")
    def influence_history(deck_id: int, influence_id: str) -> list[dict[str, Any]]:
        return hub.dna.history(influence_id)

    @app.post("/decks/{deck_id}/files", status_code=201)
    def upload_reference(deck_id: int, file: UploadFile) -> StoredFile:
        return hub.upload_reference(deck_id, file.filename or "file", read_upload(file))

    @app.get("/decks/{deck_id}/dna")
    def deck_dna(deck_id: int, format: Literal["graph", "text"] = "graph") -> dict[str, Any]:
        return hub.get_dna(deck_id, None, format)

    @app.get("/decks/{deck_id}/slides/{n}/dna")
    def slide_dna(deck_id: int, n: int, format: Literal["graph", "text"] = "graph") -> dict[str, Any]:
        return hub.get_dna(deck_id, n, format)

    add_file_routes(app, hub)


def add_file_routes(app: FastAPI, hub: Hub) -> None:
    @app.put("/slides")
    async def put_slide(path: str, request: Request, mode: Mode = "upsert") -> dict[str, Any]:
        return hub.put_slide(path, await request.body(), mode)

    @app.get("/slides")
    def read_slide(path: str) -> dict[str, Any]:
        return hub.read_slide(path)

    @app.get("/files")
    def list_files(prefix: str = "", deck: int | None = None) -> list[StoredFile]:
        return hub.files.list(prefix, deck)

    @app.get("/file")
    def get_file(path: str) -> StoredFile:
        return hub.files.get(path)

    @app.delete("/file")
    def delete_file(path: str, purge: bool = False) -> StoredFile:
        return hub.delete(path, purge)

    @app.get("/file/content")
    def file_content(path: str) -> Response:
        file, data = hub.files.read(path)
        return Response(data, media_type=file.mime)

    @app.put("/file/content")
    async def put_file(
        path: str, request: Request, mode: Mode = "upsert", deck: int | None = None
    ) -> StoredFile:
        return hub.put_file(path, await request.body(), mode, deck)

    @app.patch("/file/meta")
    def update_meta(path: str, patch: Annotated[dict[str, Any], Body()]) -> StoredFile:
        return hub.update_meta(path, patch)

    @app.post("/file/move")
    def move_file(body: Move) -> StoredFile:
        return hub.move(body.src, body.dst)

    @app.post("/files/reconcile")
    def reconcile() -> Reconciled:
        return hub.reconcile()

    @app.post("/files/{file_id}/relink")
    def relink(file_id: str, body: Relink) -> StoredFile:
        return hub.relink(file_id, body.path)

    @app.delete("/files/{file_id}", status_code=204)
    def forget(file_id: str) -> None:
        hub.forget(file_id)
