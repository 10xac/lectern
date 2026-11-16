"""Decision D10: the production guard, /health and serving the built web app."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from conftest import REPO
from fastapi.testclient import TestClient

from lectern.api import create_app
from lectern.guard import RateLimiter, RedactSecrets
from lectern.providers.fake import FakeProvider
from lectern.store import Store

ASK = {"question": "Why did the harbour cafe grow?"}


def app_client(monkeypatch: pytest.MonkeyPatch, **env: str) -> TestClient:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return TestClient(create_app(Store(), FakeProvider()), base_url="http://127.0.0.1:8000")


def deck(client: TestClient) -> int:
    pptx = (REPO / "decks" / "kettle-quarterly-review.pptx").read_bytes()
    return int(client.post("/decks", files={"file": ("k.pptx", pptx)}).json()["id"])


def test_rate_limits_daily_budget_and_size_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        "LECTERN_ASKS_PER_MINUTE": "2",
        "LECTERN_UPLOADS_PER_MINUTE": "2",
        "LECTERN_MAX_UPLOAD_MB": "1",
        "LECTERN_MAX_ASKS_PER_DAY": "3",
        "LECTERN_TRUST_PROXY": "1",
    }
    with app_client(monkeypatch, **env) as client:
        d = deck(client)
        assert client.post(f"/decks/{d}/slides/2/ask", json=ASK).status_code == 202
        assert client.post(f"/api/decks/{d}/ask", json=ASK).status_code == 202
        limited = client.post(f"/decks/{d}/slides/2/ask", json=ASK)
        assert limited.status_code == 429 and "wait a minute" in limited.json()["detail"]
        assert client.put("/slides?path=decks/x/01.md", content=b"# a").status_code == 200
        assert client.put("/slides?path=decks/x/02.md", content=b"# b").status_code == 429  # third upload
        big = client.put("/file/content?path=big.bin", content=b"x" * (2 * 1024 * 1024))
        assert big.status_code == 413
        hub = client.app.state.hub  # type: ignore[attr-defined]
        hub.jobs.budget.used = 3
        spent = client.post(f"/decks/{d}/ask", json=ASK, headers={"x-real-ip": "10.0.0.9"})
        assert spent.status_code == 429 and "daily budget" in spent.json()["detail"]


def test_trusted_proxy_ip_and_limiter() -> None:
    now = [0.0]
    limiter = RateLimiter(2, window=60, clock=lambda: now[0])
    assert limiter.allow("a") and limiter.allow("a") and not limiter.allow("a") and limiter.allow("b")
    now[0] = 61
    assert limiter.allow("a")


def test_logs_never_show_secrets() -> None:
    flt = RedactSecrets(
        {
            "LECTERN_API_KEY": "test-sentinel-key-not-real",
            "SOME_SERVICE_TOKEN": "test-sentinel-token",
            "LECTERN_DB": "x.db",
        }
    )
    record = logging.LogRecord(
        "t",
        logging.INFO,
        __file__,
        1,
        "key %s and %s in x.db",
        ("test-sentinel-key-not-real", "test-sentinel-token"),
        None,
    )
    assert flt.filter(record) and record.getMessage() == "key [redacted] and [redacted] in x.db"


def test_serves_the_built_web_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<!doctype html><title>lectern</title>")
    with app_client(monkeypatch, LECTERN_STATIC=str(tmp_path)) as client:
        assert "<title>lectern</title>" in client.get("/").text
        assert client.get("/api/decks").json() == [] and client.get("/health").status_code == 200


def test_mcp_accepts_the_public_host_name(monkeypatch: pytest.MonkeyPatch) -> None:
    init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "t", "version": "1"},
        },
    }
    headers = {"accept": "application/json, text/event-stream"}
    monkeypatch.setenv("LECTERN_HOSTS", "lectern.example.org")
    with TestClient(create_app(Store(), FakeProvider()), base_url="https://lectern.example.org") as client:
        assert client.post("/mcp/", json=init, headers=headers).status_code == 200
    monkeypatch.delenv("LECTERN_HOSTS")
    with TestClient(create_app(Store(), FakeProvider()), base_url="https://lectern.example.org") as client:
        assert client.post("/mcp/", json=init, headers=headers).status_code == 421
