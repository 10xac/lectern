"""Production safety for a deployment where every ask spends the owner's paid API keys.

* **Login** (decision D11) is on with ``LECTERN_AUTH=1`` or ``LECTERN_PUBLIC=1``: the API needs a
  user session (an HttpOnly cookie plus ``X-CSRF-Token`` on writes) and ``/mcp`` needs a personal
  access token (``Authorization: Bearer lectern_pat_…``). The web app's static files, ``/health``,
  ``/auth/login``, ``/auth/accept-invite`` and ``/auth/me`` stay open.
* Per-IP rate limits on asks (``LECTERN_ASKS_PER_MINUTE``, default 10) and uploads
  (``LECTERN_UPLOADS_PER_MINUTE``, default 20). The daily ask budget is ``jobs.DailyBudget``.
* Request bodies are capped (``LECTERN_MAX_UPLOAD_MB``, default 20) before they are read.
* ``RedactSecrets`` removes the value of every ``*_KEY``, ``*_TOKEN`` and ``*_PASSWORD`` variable
  (read at log time, so keys stored later from the web app are covered) from log records.

Client IPs come from ``X-Real-IP`` only when ``LECTERN_TRUST_PROXY=1`` (a host nginx in front).
"""

from __future__ import annotations

import hmac
import logging
import os
import re
import secrets
import time
from collections import defaultdict, deque
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from mcp.server.transport_security import TransportSecuritySettings

from lectern.users import Users, csrf_for

COOKIE = "lectern_session"
VIEWER = "lectern_viewer"
VIEWER_ID = re.compile(r"^[\w-]{16,64}$")
ASK = re.compile(r"^/decks/\d+(/slides/\d+)?/ask$")
UPLOAD = re.compile(r"^/(decks(/\d+/(files|attachments))?|slides|file/content)$")
SECRET_NAME = re.compile(r"(_KEY|_TOKEN|_PASSWORD)$")
API = (
    "/decks",
    "/jobs",
    "/files",
    "/file",
    "/slides",
    "/traces",
    "/agents",
    "/auth/",
    "/me/",
    "/admin/",
    "/oauth/",
)
OPEN_API = ("/auth/login", "/auth/accept-invite", "/auth/me")


def mcp_hosts(env: Mapping[str, str] | None = None) -> TransportSecuritySettings:
    """The MCP SDK refuses unknown Host headers (DNS rebinding). Behind nginx, list the public names
    in ``LECTERN_HOSTS`` (comma-separated, e.g. ``lectern.example.org``); localhost always works."""
    env = os.environ if env is None else env
    names = [h.strip() for h in env.get("LECTERN_HOSTS", "").split(",") if h.strip()]
    hosts = [*names, "127.0.0.1:*", "localhost:*", "127.0.0.1", "localhost"]
    origins = [f"https://{h}" for h in names] + ["http://127.0.0.1:*", "http://localhost:*"]
    return TransportSecuritySettings(allowed_hosts=hosts, allowed_origins=origins)


class RateLimiter:
    """At most ``limit`` events per ``window`` seconds per key (a sliding window, in memory)."""

    def __init__(self, limit: int, window: float = 60.0, clock: Any = time.monotonic) -> None:
        self.limit, self.window, self.clock = limit, window, clock
        self.seen: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now, times = self.clock(), self.seen[key]
        while times and now - times[0] >= self.window:
            times.popleft()
        if len(times) >= self.limit:
            return False
        times.append(now)
        return True


def client_ip(request: Request, env: Mapping[str, str]) -> str:
    if env.get("LECTERN_TRUST_PROXY") == "1" and request.headers.get("x-real-ip"):
        return request.headers["x-real-ip"]
    return request.client.host if request.client else "unknown"


def auth_on(env: Mapping[str, str]) -> bool:
    return env.get("LECTERN_AUTH") == "1" or env.get("LECTERN_PUBLIC") == "1"


def install(app: FastAPI, users: Users, env: Mapping[str, str] | None = None) -> None:
    """Add the guard middleware (each part is a no-op unless configured)."""
    env = dict(os.environ if env is None else env)
    login = auth_on(env)
    max_bytes = int(env.get("LECTERN_MAX_UPLOAD_MB", "20")) * 1024 * 1024 + 64 * 1024  # + form overhead
    asks = RateLimiter(int(env.get("LECTERN_ASKS_PER_MINUTE", "10")))
    uploads = RateLimiter(int(env.get("LECTERN_UPLOADS_PER_MINUTE", "20")))

    @app.middleware("http")
    async def guard(request: Request, call_next: Any) -> Any:
        path, method = request.url.path, request.method
        via_spa = path.startswith("/api/")  # the web app calls /api/*; one server serves both
        if via_spa:
            path = path[4:]
            request.scope["path"] = path
        if path == "/mcp":  # serve the MCP endpoint at /mcp as well as /mcp/ (no redirect for POSTs)
            path = request.scope["path"] = "/mcp/"
        refused = identify(request, users, path, method, login, via_spa)
        if refused is not None:
            return refused
        if int(request.headers.get("content-length") or 0) > max_bytes:
            return JSONResponse({"detail": "request too large"}, status_code=413)
        ip = client_ip(request, env)
        if method == "POST" and ASK.match(path) and not asks.allow(ip):
            return JSONResponse({"detail": "too many questions; wait a minute"}, status_code=429)
        if method in ("POST", "PUT") and UPLOAD.match(path) and not uploads.allow(ip):
            return JSONResponse({"detail": "too many uploads; wait a minute"}, status_code=429)
        request.state.viewer, fresh = viewer_for(request)
        response = await call_next(request)
        if fresh is not None:
            response.set_cookie(VIEWER, fresh, max_age=365 * 86400, path="/", httponly=True, samesite="lax")
        return response


def identify(
    request: Request, users: Users, path: str, method: str, login: bool, via_spa: bool
) -> Response | None:
    """Set ``request.state.user`` from the session cookie or a bearer token; refuse when login is
    required and missing. ``None`` means go on."""
    if path.startswith("/mcp"):
        bearer = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        oauth = getattr(request.app.state, "oauth", None)
        user = oauth.user_for(bearer) if bearer and oauth is not None else None
        request.state.user = user or (users.by_token(bearer) if bearer else None)
        if request.state.user is None and (login or bearer):
            # The challenge tells an MCP client (claude.ai, Claude Code) where to start OAuth.
            meta = f"{oauth.issuer}/.well-known/oauth-protected-resource/mcp" if oauth else ""
            challenge = f'Bearer realm="lectern", resource_metadata="{meta}"'
            if bearer:
                challenge += ', error="invalid_token"'
            return JSONResponse({"detail": "sign in to connect"}, status_code=401,
                                headers={"WWW-Authenticate": challenge})  # fmt: skip
        return None
    session = request.cookies.get(COOKIE, "")
    request.state.user = users.by_session(session)
    is_api = via_spa or path.startswith(API)
    if not login or not is_api or path in OPEN_API:
        return None  # the web app's own files (it shows the login form) and the open auth routes
    if request.state.user is None:
        if visitor_allowed(request, path, method):
            return None  # a shared deck: no session, no CSRF (a visitor holds nothing to forge)
        return JSONResponse({"detail": "log in first"}, status_code=401)
    if method not in ("GET", "HEAD") and not hmac.compare_digest(
        request.headers.get("x-csrf-token", "").encode(), csrf_for(session).encode()
    ):
        return JSONResponse({"detail": "missing or wrong CSRF token"}, status_code=403)
    return None


def visitor_allowed(request: Request, path: str, method: str) -> bool:
    """A signed-out visitor may list shared decks and use a deck they can see (see ``sharing.py``)."""
    sharing = getattr(request.app.state, "sharing", None)
    if sharing is None:
        return False
    if path == "/decks" and method == "GET":
        return True
    rows = request.app.state.hub.jobs.rows

    def job_deck(job_id: str) -> int | None:
        job = rows.get(job_id)
        return job.deck_id if job is not None else None

    deck_id = sharing.deck_of(path, method, job_deck)
    if deck_id is None:
        return False
    if path.endswith("/unlock"):
        return bool(sharing.get(deck_id)[0] == "password")
    return bool(sharing.can_view(deck_id, dict(request.cookies)))


def viewer_for(request: Request) -> tuple[str, str | None]:
    """``(viewer id, new cookie value or None)``: a user's own id, or an anonymous visitor's cookie.
    With login off there is one local user, and everyone shares the threads as before."""
    user = getattr(request.state, "user", None)
    if user is not None:
        return f"u{user.id}", None
    if not getattr(request.app.state, "auth_on", False):
        return "", None
    given = request.cookies.get(VIEWER, "")
    if VIEWER_ID.match(given):
        return f"v{given}", None
    fresh = secrets.token_urlsafe(18)
    return f"v{fresh}", fresh


class RedactSecrets(logging.Filter):
    """Replace secret values (from ``*_KEY``, ``*_TOKEN``, ``*_PASSWORD`` variables) in log records."""

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        super().__init__()
        self.env = os.environ if env is None else env

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact inside the message and each argument, keeping their shape: formatters such as
        uvicorn's access formatter unpack ``record.args`` and break if it is replaced."""
        secrets = [v for k, v in self.env.items() if SECRET_NAME.search(k) and len(v) >= 6]

        def clean(value: Any) -> Any:
            if not isinstance(value, str):
                return value
            for secret in secrets:
                value = value.replace(secret, "[redacted]")
            return value

        if secrets:
            record.msg = clean(record.msg)
            if isinstance(record.args, tuple):
                record.args = tuple(clean(a) for a in record.args)
            elif isinstance(record.args, dict):
                record.args = {k: clean(v) for k, v in record.args.items()}
        return True


def redact_logs() -> None:
    """Install ``RedactSecrets`` on the root, lectern and uvicorn loggers. Logger filters survive
    uvicorn's own logging setup, which replaces handlers but keeps them."""
    flt = RedactSecrets()
    for name in ("", "lectern", "uvicorn", "uvicorn.error", "uvicorn.access", "httpx"):
        logging.getLogger(name).addFilter(flt)
