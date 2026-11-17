"""Decision D13: OAuth for MCP connectors, along the path claude.ai takes."""

from __future__ import annotations

import base64
import hashlib
import secrets
from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from lectern.api import create_app
from lectern.providers.fake import FakeProvider
from lectern.store import Store

BASE = "http://127.0.0.1:8000"
CALLBACK = "https://claude.ai/api/mcp/auth_callback"
INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "claude-ai", "version": "1"},
    },
}
MCP = {"accept": "application/json, text/event-stream", "content-type": "application/json"}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("LECTERN_AUTH", "1")
    monkeypatch.delenv("LECTERN_PUBLIC_URL", raising=False)
    with TestClient(create_app(Store(), FakeProvider()), base_url=BASE) as c:
        yield c


def query(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


def connect(client: TestClient) -> tuple[dict[str, Any], str]:
    """Register, authorize, consent and exchange: returns (tokens, client_id)."""
    reg = client.post(
        "/register",
        json={"redirect_uris": [CALLBACK], "client_name": "Claude", "token_endpoint_auth_method": "none"},
    )
    assert reg.status_code == 201, reg.text
    client_id = reg.json()["client_id"]
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    auth = client.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": CALLBACK,
            "state": "s1",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "resource": f"{BASE}/mcp",
        },
        follow_redirects=False,
    )
    assert auth.status_code == 302 and auth.headers["location"].startswith(f"{BASE}/connect/authorize?txn=")
    txn = query(auth.headers["location"])["txn"]
    users = client.app.state.hub.users  # type: ignore[attr-defined]
    _, invite = users.invite("ai@example.org")
    csrf = client.post(
        "/auth/accept-invite", json={"token": invite, "password": "a long enough password"}
    ).json()["csrf"]
    view = client.get("/oauth/txn", params={"txn": txn}).json()
    assert view == {"client": "Claude", "redirect_host": "claude.ai", "scopes": ["lectern"]}
    done = client.post(
        "/oauth/complete", json={"txn": txn, "approve": True}, headers={"X-CSRF-Token": csrf}
    ).json()
    back = query(done["redirect_to"])
    assert done["redirect_to"].startswith(CALLBACK) and back["state"] == "s1" and back["iss"] == BASE
    tokens = client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": back["code"],
            "client_id": client_id,
            "code_verifier": verifier,
            "redirect_uri": CALLBACK,
            "resource": f"{BASE}/mcp",
        },
    )
    assert tokens.status_code == 200, tokens.text
    again = client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": back["code"],
            "client_id": client_id,
            "code_verifier": verifier,
            "redirect_uri": CALLBACK,
        },
    )
    assert again.status_code == 400  # codes are single use
    return tokens.json(), client_id


def test_discovery_and_the_challenge(client: TestClient) -> None:
    unauth = client.post("/mcp", json=INIT, headers=MCP)
    assert unauth.status_code == 401
    assert (
        f'resource_metadata="{BASE}/.well-known/oauth-protected-resource/mcp"'
        in unauth.headers["www-authenticate"]
    )
    resource = client.get("/.well-known/oauth-protected-resource/mcp").json()
    assert resource["resource"] == f"{BASE}/mcp" and resource["authorization_servers"] == [BASE]
    meta = client.get("/.well-known/oauth-authorization-server").json()
    assert meta["issuer"] == BASE  # exactly the metadata URL's origin, and the iss we return
    assert meta["registration_endpoint"] == f"{BASE}/register" and meta[
        "code_challenge_methods_supported"
    ] == ["S256"]
    assert meta["authorization_response_iss_parameter_supported"] is True
    bad = client.post(
        "/register", json={"redirect_uris": ["https://claude.ai.evil.example/api/mcp/auth_callback"]}
    )
    assert bad.status_code == 400 and "not allowed" in bad.text
    loopback = client.post("/register", json={"redirect_uris": ["http://127.0.0.1:33418/callback"]})
    assert loopback.status_code == 201  # Claude Code and other local clients


def test_the_claude_ai_flow_end_to_end(client: TestClient) -> None:
    tokens, client_id = connect(client)
    assert tokens["access_token"].startswith("lectern_oa_") and tokens["refresh_token"].startswith(
        "lectern_or_"
    )
    bearer = MCP | {"authorization": f"Bearer {tokens['access_token']}"}
    assert client.post("/mcp", json=INIT, headers=bearer).status_code == 200
    stale = client.post("/mcp", json=INIT, headers=MCP | {"authorization": "Bearer lectern_oa_nope"})
    assert stale.status_code == 401 and 'error="invalid_token"' in stale.headers["www-authenticate"]
    fresh = client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "client_id": client_id,
        },
    ).json()
    assert fresh["access_token"] != tokens["access_token"]
    reuse = client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "client_id": client_id,
        },
    )
    assert reuse.status_code == 400  # a rotated refresh token presented again ends the whole family
    assert (
        client.post(
            "/mcp", json=INIT, headers=MCP | {"authorization": f"Bearer {fresh['access_token']}"}
        ).status_code
        == 401
    )


def test_connections_can_be_ended_by_their_owner_or_an_admin(client: TestClient) -> None:
    tokens, client_id = connect(client)
    bearer = MCP | {"authorization": f"Bearer {tokens['access_token']}"}
    mine = client.get("/me/connections").json()
    assert [c["client"] for c in mine] == ["Claude"]
    csrf = client.get("/auth/me").json()["csrf"]
    assert (
        client.delete(f"/me/connections/{mine[0]['id']}", headers={"X-CSRF-Token": csrf}).status_code == 204
    )
    assert client.post("/mcp", json=INIT, headers=bearer).status_code == 401
    oauth = client.app.state.oauth  # type: ignore[attr-defined]
    client_id = oauth.clients()[0]["id"]
    tokens2 = client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "client_id": client_id,
        },
    )
    assert tokens2.status_code == 400  # the connection was ended: its refresh token is dead too
    oauth.set_client_disabled(client_id, True)
    assert oauth.clients()[0]["disabled"] is True
    assert client.post("/register", json={"redirect_uris": [CALLBACK]}).status_code == 201  # others still can


def test_deny_redirects_with_access_denied_and_iss(client: TestClient) -> None:
    reg = client.post("/register", json={"redirect_uris": [CALLBACK], "client_name": "Claude"}).json()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(b"v" * 50).digest()).rstrip(b"=").decode()
    auth = client.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": reg["client_id"],
            "redirect_uri": CALLBACK,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": "x",
        },
        follow_redirects=False,
    )
    txn = query(auth.headers["location"])["txn"]
    users = client.app.state.hub.users  # type: ignore[attr-defined]
    _, invite = users.invite("d@example.org")
    csrf = client.post(
        "/auth/accept-invite", json={"token": invite, "password": "a long enough password"}
    ).json()["csrf"]
    client.get("/oauth/txn", params={"txn": txn})
    done = client.post(
        "/oauth/complete", json={"txn": txn, "approve": False}, headers={"X-CSRF-Token": csrf}
    ).json()
    assert query(done["redirect_to"]) == {"error": "access_denied", "state": "x", "iss": BASE}
    assert (
        client.post(
            "/oauth/complete", json={"txn": txn, "approve": True}, headers={"X-CSRF-Token": csrf}
        ).status_code
        == 404
    )
