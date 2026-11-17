"""Sharing a deck (decision D14): private, public, or public behind a simple password.

* **private** (the default): only signed-in users see it.
* **public**: anyone with the link can view it, read its DNA and ask its slides' agents.
* **password**: the same, after entering the deck's password once (``POST /decks/{d}/unlock``). The
  browser then holds a cookie derived from the password's scrypt hash, so changing the password
  locks everyone out again.

Visitors' questions spend the owner's model budget, so the per-IP limits and the daily ask budget
apply to them too. Each visitor gets an anonymous ``lectern_viewer`` cookie, which keeps their
chat threads apart from everyone else's.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
from typing import Any, Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from lectern.files import FileError
from lectern.guard import RateLimiter, client_ip
from lectern.store import Store
from lectern.users import MAX_PASSWORD, hash_password, verify_password

Visibility = Literal["private", "public", "password"]
# What a visitor may do on a deck they can see: read it, its threads, DNA and traces; ask; follow jobs.
PUBLIC_GET = re.compile(r"^/decks/(\d+)(/slides/\d+)?(/messages|/dna|/influences)?$")
PUBLIC_ASK = re.compile(r"^/decks/(\d+)(/slides/\d+)?/ask$")
UNLOCK = re.compile(r"^/decks/(\d+)/unlock$")
JOB = re.compile(r"^/jobs/(\w+)(/events)?$")
TRACE = re.compile(r"^/traces/(\d+)$")


class ShareBody(BaseModel):
    visibility: Visibility
    password: str | None = Field(default=None, max_length=MAX_PASSWORD)


class Unlock(BaseModel):
    password: str = Field(max_length=MAX_PASSWORD)


def cookie_name(deck_id: int) -> str:
    return f"lectern_deck_{deck_id}"


class Sharing:
    def __init__(self, store: Store) -> None:
        self.store = store

    def get(self, deck_id: int) -> tuple[Visibility, str | None]:
        with self.store.tx() as db:
            row = db.execute("SELECT visibility, share_hash FROM decks WHERE id = ?", (deck_id,)).fetchone()
        if row is None:
            raise FileError(404, f"no deck {deck_id}")
        return (row["visibility"] or "private"), row["share_hash"]

    def set(self, deck_id: int, visibility: Visibility, password: str | None) -> dict[str, Any]:
        _, old = self.get(deck_id)
        if visibility == "password" and not password and not old:
            raise FileError(422, "a password-protected deck needs a password")
        if password is not None and visibility == "password" and len(password) < 4:
            raise FileError(422, "use a password of at least 4 characters")
        share_hash = (hash_password(password) if password else old) if visibility == "password" else None
        with self.store.tx() as db:
            db.execute(
                "UPDATE decks SET visibility = ?, share_hash = ? WHERE id = ?",
                (visibility, share_hash, deck_id),
            )
        return {"visibility": visibility, "has_password": share_hash is not None}

    def token(self, deck_id: int, share_hash: str) -> str:
        return hashlib.sha256(f"lectern-share:{deck_id}:{share_hash}".encode()).hexdigest()

    def unlock(self, deck_id: int, password: str) -> str:
        visibility, share_hash = self.get(deck_id)
        if visibility != "password" or share_hash is None:
            raise FileError(404, f"no deck {deck_id}")
        if not verify_password(share_hash, password):
            raise FileError(403, "wrong password")
        return self.token(deck_id, share_hash)

    def can_view(self, deck_id: int, cookies: dict[str, str]) -> bool:
        try:
            visibility, share_hash = self.get(deck_id)
        except FileError:
            return False
        if visibility == "public":
            return True
        if visibility == "password" and share_hash:
            given = cookies.get(cookie_name(deck_id), "")
            return hmac.compare_digest(given.encode(), self.token(deck_id, share_hash).encode())
        return False

    def visible(self) -> list[dict[str, Any]]:
        """Decks a visitor may know about: public and password-protected ones (not private)."""
        with self.store.tx() as db:
            rows = db.execute(
                "SELECT id, title, source, visibility FROM decks WHERE visibility IN"
                " ('public', 'password') ORDER BY id DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def deck_of(self, path: str, method: str, job_deck: Any) -> int | None:
        """The deck a visitor's request is about, if it is one a visitor may make; else None."""
        for pattern, verb in ((PUBLIC_GET, "GET"), (PUBLIC_ASK, "POST"), (UNLOCK, "POST")):
            m = pattern.match(path)
            if m and method == verb:
                return int(m.group(1))
        m = JOB.match(path)
        if m and method == "GET":
            found = job_deck(m.group(1))
            return int(found) if found is not None else None
        m = TRACE.match(path)
        if m and method == "GET":
            with self.store.tx() as db:
                row = db.execute("SELECT deck_id FROM traces WHERE id = ?", (int(m.group(1)),)).fetchone()
            return int(row["deck_id"]) if row and row["deck_id"] is not None else None
        return None


def add_sharing_routes(app: FastAPI, sharing: Sharing) -> None:
    unlocks = RateLimiter(10)

    @app.get("/decks/{deck_id}/sharing")
    def get_sharing(deck_id: int) -> dict[str, Any]:
        visibility, share_hash = sharing.get(deck_id)
        return {"visibility": visibility, "has_password": share_hash is not None}

    @app.put("/decks/{deck_id}/sharing")
    def put_sharing(deck_id: int, body: ShareBody, request: Request) -> dict[str, Any]:
        if getattr(request.state, "user", None) is None and request.app.state.auth_on:
            raise FileError(401, "log in first")
        return sharing.set(deck_id, body.visibility, body.password)

    @app.post("/decks/{deck_id}/unlock")
    def unlock(deck_id: int, body: Unlock, request: Request) -> JSONResponse:
        if not unlocks.allow(client_ip(request, os.environ)):
            raise FileError(429, "too many attempts; try again later")
        token = sharing.unlock(deck_id, body.password)
        resp = JSONResponse({"unlocked": True})
        secure = request.url.scheme == "https"
        resp.set_cookie(
            cookie_name(deck_id),
            token,
            max_age=30 * 86400,
            path="/",
            httponly=True,
            samesite="lax",
            secure=secure,
        )
        return resp
