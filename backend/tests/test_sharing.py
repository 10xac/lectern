"""Decision D14: private, public and password-protected decks; visitors' own threads; slide edits."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from conftest import REPO
from fastapi.testclient import TestClient

from lectern.api import create_app
from lectern.providers.fake import FakeProvider
from lectern.store import Store

BASE = "http://127.0.0.1:8000"
ASK = {"question": "Why did the harbour cafe grow?"}


@pytest.fixture
def owner(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("LECTERN_AUTH", "1")
    with TestClient(create_app(Store(), FakeProvider()), base_url=BASE) as c:
        users = c.app.state.hub.users  # type: ignore[attr-defined]
        _, token = users.invite("owner@example.org", "admin")
        csrf = c.post(
            "/auth/accept-invite", json={"token": token, "password": "a long enough password"}
        ).json()["csrf"]
        c.headers["X-CSRF-Token"] = csrf
        yield c


def deck(owner: TestClient) -> int:
    pptx = (REPO / "decks" / "kettle-quarterly-review.pptx").read_bytes()
    return int(owner.post("/decks", files={"file": ("k.pptx", pptx)}).json()["id"])


def visitor(owner: TestClient) -> TestClient:
    return TestClient(owner.app, base_url=BASE)


def test_public_decks_are_open_and_visitors_keep_their_own_threads(owner: TestClient) -> None:
    d = deck(owner)
    guest = visitor(owner)
    assert (
        guest.get("/decks").json() == [] and guest.get(f"/decks/{d}").status_code == 401
    )  # private by default
    assert owner.put(f"/decks/{d}/sharing", json={"visibility": "public"}).json()["visibility"] == "public"
    assert [x["id"] for x in guest.get("/decks").json()] == [d]
    assert guest.get(f"/decks/{d}").json()["visibility"] == "public"
    job = guest.post(f"/decks/{d}/slides/2/ask?wait=true", json=ASK).json()
    assert job["status"] == "answered" and guest.get(f"/jobs/{job['id']}").status_code == 200
    assert guest.get(f"/decks/{d}/slides/2/dna?format=text").status_code == 200
    assert [m["role"] for m in guest.get(f"/decks/{d}/slides/2/messages").json()] == ["user", "agent"]
    assert owner.get(f"/decks/{d}/slides/2/messages").json() == []  # the owner's thread is their own
    other = visitor(owner)
    assert other.get(f"/decks/{d}/slides/2/messages").json() == []  # and so is every other visitor's
    assert (
        guest.patch(f"/decks/{d}/slides/2", json={"notes": "x"}).status_code == 401
    )  # visitors only read and ask
    assert guest.put(f"/decks/{d}/sharing", json={"visibility": "private"}).status_code == 401
    assert guest.post(f"/decks/{d}/influences", json={}).status_code == 401
    owner.put(f"/decks/{d}/sharing", json={"visibility": "private"})
    assert guest.get(f"/decks/{d}").status_code == 401 and guest.get(f"/jobs/{job['id']}").status_code == 401


def test_password_decks_unlock_once_and_lock_again_when_the_password_changes(owner: TestClient) -> None:
    d = deck(owner)
    assert owner.put(f"/decks/{d}/sharing", json={"visibility": "password"}).status_code == 422  # needs one
    owner.put(f"/decks/{d}/sharing", json={"visibility": "password", "password": "harbour"})
    guest = visitor(owner)
    assert [x["visibility"] for x in guest.get("/decks").json()] == ["password"]
    assert guest.get(f"/decks/{d}").status_code == 401
    assert guest.post(f"/decks/{d}/unlock", json={"password": "wrong"}).status_code == 403
    assert guest.post(f"/decks/{d}/unlock", json={"password": "harbour"}).json() == {"unlocked": True}
    assert guest.get(f"/decks/{d}").status_code == 200
    asked = guest.post(f"/decks/{d}/ask?wait=true", json={"question": "Summarise the deck"})
    assert asked.status_code == 202 and asked.json()["status"] in ("answered", "abstained")
    owner.put(f"/decks/{d}/sharing", json={"visibility": "password", "password": "new-one"})
    assert guest.get(f"/decks/{d}").status_code == 401


def test_users_edit_titles_and_notes_on_any_deck(owner: TestClient) -> None:
    d = deck(owner)
    edited = owner.patch(
        f"/decks/{d}/slides/2", json={"notes": "Mention the ferry.", "title": "Revenue"}
    ).json()
    assert edited["notes"] == "Mention the ferry." and edited["title"] == "Revenue"
    folder = owner.put("/slides?path=decks/talk/01.md", content=b"# One\nBody").json()["deck_id"]
    owner.patch(f"/decks/{folder}/slides/1", json={"notes": "Say hello."})
    assert owner.get("/file?path=decks/talk/01.md").json()["meta"] == {"notes": "Say hello."}
    assert owner.get(f"/decks/{folder}").json()["slides"][0]["notes"] == "Say hello."
