"""Managing decks and slides over REST (the web app's menus; MCP has the same tools):

PATCH  /decks/{d}                      {title}                     rename
DELETE /decks/{d}                                                  delete, with everything in it
PATCH  /decks/{d}/slides/{n}           {title?, body?, notes?, html?}
POST   /decks/{d}/slides               {at?, title?, body?, notes?, html?}   insert (at: 1-based)
POST   /decks/{d}/slides/{n}/duplicate                             a copy right after it
POST   /decks/{d}/slides/{n}/move      {to}
DELETE /decks/{d}/slides/{n}
GET    /decks/{d}/original             the uploaded file, as it was uploaded
GET    /media/{d}/{name}               a picture drawn on a slide (an unguessable name; no login,
                                       because a sandboxed slide frame sends no cookies)
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import FastAPI, Response
from pydantic import BaseModel, Field

from lectern.files import FileError
from lectern.hub import Hub

MEDIA_NAME = re.compile(r"^[0-9a-f]{24}\.[a-z0-9]{1,5}$")


class DeckEdit(BaseModel):
    title: str = Field(min_length=1, max_length=300)


class SlideFields(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    body: str | None = Field(default=None, max_length=20_000)
    notes: str | None = Field(default=None, max_length=20_000)
    html: str | None = Field(default=None, max_length=2_000_000)


class NewSlide(SlideFields):
    at: int | None = None


class Move(BaseModel):
    to: int


def add_deck_routes(app: FastAPI, hub: Hub) -> None:
    @app.patch("/decks/{deck_id}")
    def rename(deck_id: int, body: DeckEdit) -> dict[str, Any]:
        return hub.rename_deck(deck_id, body.title)

    @app.delete("/decks/{deck_id}", status_code=204)
    def delete(deck_id: int) -> None:
        hub.delete_deck(deck_id)

    @app.patch("/decks/{deck_id}/slides/{n}")
    def update(deck_id: int, n: int, body: SlideFields) -> dict[str, Any]:
        return hub.update_slide(deck_id, n, body.model_dump(exclude_none=True))

    @app.post("/decks/{deck_id}/slides", status_code=201)
    def insert(deck_id: int, body: NewSlide) -> dict[str, Any]:
        return hub.insert_slide(deck_id, body.at, body.model_dump(exclude={"at"}, exclude_none=True))

    @app.post("/decks/{deck_id}/slides/{n}/duplicate", status_code=201)
    def duplicate(deck_id: int, n: int) -> dict[str, Any]:
        return hub.duplicate_slide(deck_id, n)

    @app.post("/decks/{deck_id}/slides/{n}/move")
    def move(deck_id: int, n: int, body: Move) -> dict[str, Any]:
        return hub.move_slide(deck_id, n, body.to)

    @app.delete("/decks/{deck_id}/slides/{n}")
    def delete_slide(deck_id: int, n: int) -> dict[str, Any]:
        return hub.delete_slide(deck_id, n)

    @app.get("/decks/{deck_id}/original")
    def original(deck_id: int) -> Response:
        deck = hub.deck(deck_id)
        if deck.file_id is None:
            raise FileError(404, "this deck has no uploaded original (it was built slide by slide)")
        file, data = hub.files.read(hub.files.by_id(deck.file_id).path)
        name = file.path.rsplit("/", 1)[-1].replace('"', "")
        return Response(
            data, media_type=file.mime, headers={"Content-Disposition": f'attachment; filename="{name}"'}
        )

    @app.get("/media/{deck_id}/{name}")
    def media(deck_id: int, name: str) -> Response:
        if not MEDIA_NAME.match(name):
            raise FileError(404, "no such picture")
        file, data = hub.files.read(f"uploads/{deck_id}/media/{name}")
        return Response(data, media_type=file.mime, headers={"Cache-Control": "private, max-age=86400"})
