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
import time
from collections import defaultdict, deque
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from mcp.server.transport_security import TransportSecuritySettings

from lectern.users import Users, csrf_for

COOKIE = "lectern_session"
ASK = re.compile(r"^/decks/\d+(/slides/\d+)?/ask$")
UPLOAD = re.compile(r"^/(decks(/\d+/(files|attachments))?|slides|file/content)$")
SECRET_NAME = re.compile(r"(_KEY|_TOKEN|_PASSWORD)$")
API = ("/decks", "/jobs", "/files", "/file", "/slides", "/traces", "/agents", "/auth/", "/me/", "/admin/")
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
        return await call_next(request)


def identify(
    request: Request, users: Users, path: str, method: str, login: bool, via_spa: bool
) -> Response | None:
    """Set ``request.state.user`` from the session cookie or a bearer token; refuse when login is
    required and missing. ``None`` means go on."""
    if path.startswith("/mcp"):
        bearer = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        request.state.user = users.by_token(bearer) if bearer else None
        if login and request.state.user is None:
            return JSONResponse({"detail": "a personal access token is required"}, status_code=401)
        return None
    session = request.cookies.get(COOKIE, "")
    request.state.user = users.by_session(session)
    is_api = via_spa or path.startswith(API)
    if not login or not is_api or path in OPEN_API:
        return None  # the web app's own files (it shows the login form) and the open auth routes
    if request.state.user is None:
        return JSONResponse({"detail": "log in first"}, status_code=401)
    if method not in ("GET", "HEAD") and not hmac.compare_digest(
        request.headers.get("x-csrf-token", "").encode(), csrf_for(session).encode()
    ):
        return JSONResponse({"detail": "missing or wrong CSRF token"}, status_code=403)
    return None


class RedactSecrets(logging.Filter):
    """Replace secret values (from ``*_KEY``, ``*_TOKEN``, ``*_PASSWORD`` variables) in log records."""

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        super().__init__()
        self.env = os.environ if env is None else env

    def filter(self, record: logging.LogRecord) -> bool:
        secrets = [v for k, v in self.env.items() if SECRET_NAME.search(k) and len(v) >= 6]
        if secrets:
            text = record.getMessage()
            for secret in secrets:
                text = text.replace(secret, "[redacted]")
            record.msg, record.args = text, None
        return True


def redact_logs() -> None:
    """Install ``RedactSecrets`` on the root, lectern and uvicorn loggers. Logger filters survive
    uvicorn's own logging setup, which replaces handlers but keeps them."""
    flt = RedactSecrets()
    for name in ("", "lectern", "uvicorn", "uvicorn.error", "uvicorn.access", "httpx"):
        logging.getLogger(name).addFilter(flt)
