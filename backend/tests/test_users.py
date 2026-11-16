"""Decisions D11 and D12: users and invites, sessions and CSRF, personal tokens, managed settings."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from lectern import cli
from lectern.api import create_app
from lectern.providers.fake import FakeProvider
from lectern.settings import SECRETS, SETTINGS
from lectern.store import Store

PASSWORD = "correct horse battery"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    for name in (*SETTINGS, *SECRETS):  # settings write the environment: register each name so pytest
        monkeypatch.setenv(name, "")  # restores it (delenv alone does not record an absent variable)
        monkeypatch.delenv(name)
    monkeypatch.setenv("LECTERN_AUTH", "1")
    monkeypatch.setenv("LECTERN_SECRET_KEY", Fernet.generate_key().decode())
    with TestClient(create_app(Store(), FakeProvider())) as c:
        yield c


def sign_in(client: TestClient, email: str, role: str = "member") -> dict[str, str]:
    """Invite (as the CLI or an admin would), accept the link, and return the CSRF header."""
    users = client.app.state.hub.users  # type: ignore[attr-defined]
    _, token = users.invite(email, role)  # type: ignore[arg-type]
    body = client.post("/auth/accept-invite", json={"token": token, "password": PASSWORD}).json()
    return {"X-CSRF-Token": body["csrf"]}


def test_login_sessions_csrf_and_admins(client: TestClient) -> None:
    assert client.get("/auth/me").json() == {"auth": True, "user": None, "csrf": None}
    assert client.get("/decks").status_code == 401 and client.get("/api/decks").status_code == 401
    admin = sign_in(client, "Admin@Example.org", "admin")
    assert client.get("/auth/me").json()["user"]["email"] == "admin@example.org"
    assert client.put("/slides?path=decks/a/01.md", content=b"# One").status_code == 403  # no CSRF token
    assert client.put("/slides?path=decks/a/01.md", content=b"# One", headers=admin).status_code == 200
    invited = client.post("/auth/users", json={"email": "m@example.org"}, headers=admin).json()
    token = invited["invite_url"].split("#invite=")[1]
    client.post("/auth/logout", headers=admin)
    assert client.get("/decks").status_code == 401
    member = client.post("/auth/accept-invite", json={"token": token, "password": PASSWORD}).json()
    assert member["user"]["role"] == "member" and client.get("/decks").status_code == 200
    assert client.get("/auth/users").status_code == 403  # only admins manage users
    assert client.post("/auth/accept-invite", json={"token": token, "password": PASSWORD}).status_code == 400
    assert (
        client.post("/auth/accept-invite", json={"token": "x" * 30, "password": "short"}).status_code == 422
    )
    users = client.app.state.hub.users  # type: ignore[attr-defined]
    users.update(member["user"]["id"], status="disabled")
    assert client.get("/decks").status_code == 401  # disabling ends the session at once
    with pytest.raises(Exception, match="at least one active admin"):
        users.update(1, role="member")


def test_wrong_passwords_lock_the_account(client: TestClient) -> None:
    sign_in(client, "a@example.org")
    for _ in range(5):
        assert (
            client.post("/auth/login", json={"email": "a@example.org", "password": "wrong"}).status_code
            == 401
        )
    assert (
        client.post("/auth/login", json={"email": "a@example.org", "password": PASSWORD}).status_code == 429
    )
    unknown = client.post("/auth/login", json={"email": "nobody@example.org", "password": "wrong"})
    assert unknown.status_code == 401 and unknown.json()["detail"] == "invalid email or password"


def test_personal_tokens_are_shown_once(client: TestClient) -> None:
    csrf = sign_in(client, "t@example.org")
    made = client.post("/me/tokens", json={"name": "claude code", "days": 30}, headers=csrf).json()
    assert made["secret"].startswith("lectern_pat_") and "secret" not in str(client.get("/me/tokens").json())
    assert client.post("/me/tokens", json={"name": "x", "days": 365}, headers=csrf).status_code == 422
    assert client.delete(f"/me/tokens/{made['token']['id']}", headers=csrf).status_code == 204
    assert client.get("/me/tokens").json()[0]["revoked_at"] is not None


def test_admins_manage_models_and_keys(client: TestClient) -> None:
    import os

    admin = sign_in(client, "admin@example.org", "admin")
    put = client.put(
        "/admin/settings/LECTERN_API_KEY", json={"value": "test-sentinel-key-not-real"}, headers=admin
    )
    key = next(k for k in put.json()["keys"] if k["name"] == "LECTERN_API_KEY")
    assert key == {"name": "LECTERN_API_KEY", "set": True, "source": "lectern", "last4": "real"}
    assert (
        "test-sentinel-key-not-real" not in put.text
        and os.environ["LECTERN_API_KEY"] == "test-sentinel-key-not-real"
    )
    client.put("/admin/settings/LECTERN_PROVIDER", json={"value": "openai_compat"}, headers=admin)
    got = client.get("/admin/settings").json()
    assert got["system1"]["kind"] == "jev" and got["system1"]["key"] == "set"  # OpenRouter by default
    stored = client.app.state.hub.store  # type: ignore[attr-defined]
    with stored.tx() as db:
        assert "not-real" not in db.execute("SELECT value FROM settings WHERE secret = 1").fetchone()[0]
    client.put("/admin/settings/LECTERN_API_KEY", json={"value": None}, headers=admin)
    assert "LECTERN_API_KEY" not in os.environ
    assert client.put("/admin/settings/PATH", json={"value": "x"}, headers=admin).status_code == 404


def test_cli_seeds_the_first_admin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LECTERN_DB", str(tmp_path / "u.db"))
    monkeypatch.setenv("LECTERN_BLOBS", str(tmp_path / "blobs"))
    assert cli.main(["users", "create-admin", "boss@example.org"]) == 0
    link = capsys.readouterr().out.strip().splitlines()[-1]
    assert link.startswith("http://127.0.0.1:8000/#invite=")
    assert cli.main(["users", "create-admin", "boss@example.org"]) == 0  # still invited: a new link
    assert cli.main(["users", "list"]) == 0 and "boss@example.org  admin  invited" in capsys.readouterr().out
