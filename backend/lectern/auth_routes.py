"""Login, invites, users (admins) and personal MCP tokens (decision D11). See ``users.py``.

POST   /auth/login            {email, password}      → session cookie + {user, csrf}
POST   /auth/accept-invite    {token, password}      → session cookie + {user, csrf}
POST   /auth/logout
GET    /auth/me               {auth, user, csrf}     (auth: whether login is required at all)
GET    /auth/users                                   admins: everyone
POST   /auth/users            {email, role}          admins: invite → {user, invite_url} (shown once)
POST   /auth/users/{id}/invite                       admins: a new link (also a password reset)
PATCH  /auth/users/{id}       {role?, status?}       admins: promote, demote, disable, enable
GET    /admin/settings                               admins: models and keys (keys: set/unset, last 4)
PUT    /admin/settings/{name} {value}                admins: store or (null) remove one; applies at once
GET    /me/tokens  POST /me/tokens {name, days} → {token, secret} (shown once)  DELETE /me/tokens/{id}
"""

from __future__ import annotations

import os
from typing import Any, Literal

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from lectern.files import FileError
from lectern.guard import RateLimiter, client_ip
from lectern.jobs.system1 import resolve_system1
from lectern.settings import Settings
from lectern.users import MAX_PASSWORD, SESSION_DAYS, Role, User, Users, csrf_for

COOKIE = "lectern_session"


class Login(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=MAX_PASSWORD)


class Accept(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(max_length=MAX_PASSWORD)


class Invite(BaseModel):
    email: str = Field(max_length=320)
    role: Role = "member"


class Change(BaseModel):
    role: Role | None = None
    status: Literal["active", "disabled"] | None = None


class NewToken(BaseModel):
    name: str = Field(max_length=100)
    days: int = 30


def invite_url(request: Request, token: str) -> str:
    """The token rides in the fragment, which browsers never send to a server."""
    base = os.environ.get("LECTERN_PUBLIC_URL") or str(request.base_url).rstrip("/")
    return f"{base.rstrip('/')}/#invite={token}"


def current(request: Request) -> User:
    user: User | None = getattr(request.state, "user", None)
    if user is None:
        raise FileError(401, "log in first")
    return user


LOCAL = User(id=0, email="local", role="admin", status="active")  # login off: the one local user


def admin(request: Request) -> User:
    user = current(request) if request.app.state.auth_on else LOCAL
    if user.role != "admin":
        raise FileError(403, "only admins manage users")
    return user


class SettingValue(BaseModel):
    value: str | None = Field(default=None, max_length=4000)


def add_auth_routes(app: FastAPI, users: Users, settings: Settings, auth_on: bool) -> None:
    app.state.auth_on = auth_on
    logins = RateLimiter(int(os.environ.get("LECTERN_LOGINS_PER_MINUTE", "10")))
    secure = os.environ.get("LECTERN_PUBLIC") == "1"

    def session(user: User, token: str) -> Response:
        resp = JSONResponse({"user": user.model_dump(), "csrf": csrf_for(token)})
        resp.set_cookie(
            COOKIE,
            token,
            max_age=SESSION_DAYS * 86400,
            path="/",
            httponly=True,
            samesite="strict",
            secure=secure,
        )
        return resp

    @app.post("/auth/login")
    def login(body: Login, request: Request) -> Response:
        if not logins.allow(client_ip(request, os.environ)):
            raise FileError(429, "too many attempts; try again later")
        return session(*users.login(body.email, body.password))

    @app.post("/auth/accept-invite")
    def accept(body: Accept) -> Response:
        return session(*users.accept(body.token, body.password))

    @app.post("/auth/logout", status_code=204)
    def logout(request: Request, response: Response) -> None:
        users.logout(request.cookies.get(COOKIE, ""))
        response.delete_cookie(COOKIE, path="/")

    @app.get("/auth/me")
    def me(request: Request) -> dict[str, Any]:
        user: User | None = getattr(request.state, "user", None)
        csrf = csrf_for(request.cookies[COOKIE]) if user and COOKIE in request.cookies else None
        return {"auth": auth_on, "user": user.model_dump() if user else None, "csrf": csrf}

    add_admin_routes(app, users, settings)


def add_admin_routes(app: FastAPI, users: Users, settings: Settings) -> None:
    """Admins: users and the model settings. Everyone: their own access tokens."""

    @app.get("/auth/users")
    def list_users(request: Request) -> list[User]:
        admin(request)
        return users.all_users()

    @app.post("/auth/users", status_code=201)
    def invite(body: Invite, request: Request) -> dict[str, Any]:
        admin(request)
        user, token = users.invite(body.email, body.role)
        return {"user": user.model_dump(), "invite_url": invite_url(request, token)}

    @app.post("/auth/users/{user_id}/invite")
    def reinvite(user_id: int, request: Request) -> dict[str, Any]:
        admin(request)
        user, token = users.invite(users.get(user_id).email)
        return {"user": user.model_dump(), "invite_url": invite_url(request, token)}

    @app.patch("/auth/users/{user_id}")
    def change(user_id: int, body: Change, request: Request) -> User:
        admin(request)
        return users.update(user_id, body.role, body.status)

    @app.get("/admin/settings")
    def get_settings(request: Request) -> dict[str, Any]:
        admin(request)
        return settings.public() | {"system1": resolve_system1(os.environ).public(os.environ)}

    @app.put("/admin/settings/{name}")
    def put_setting(name: str, body: SettingValue, request: Request) -> dict[str, Any]:
        settings.set(name, body.value, admin(request).email)
        return get_settings(request)

    @app.get("/me/tokens")
    def my_tokens(request: Request) -> list[dict[str, Any]]:
        return users.tokens(current(request).id)

    @app.post("/me/tokens", status_code=201)
    def new_token(body: NewToken, request: Request) -> dict[str, Any]:
        token, secret = users.create_token(current(request).id, body.name, body.days)
        return {"token": token, "secret": secret}

    @app.delete("/me/tokens/{token_id}", status_code=204)
    def revoke(token_id: str, request: Request) -> None:
        users.revoke_token(current(request).id, token_id)
