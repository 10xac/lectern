"""The HTTP API through FastAPI's TestClient (in-memory store, fake provider, fake clock)."""

import pytest
from conftest import FIXTURES, REPO, FakeClock
from fastapi.testclient import TestClient

from lectern import api
from lectern.api import create_app
from lectern.providers.fake import FakeProvider
from lectern.store import Store


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(Store(), FakeProvider(), FakeClock()))


def upload(client: TestClient, path: str) -> dict:  # type: ignore[type-arg]
    full = FIXTURES / path if (FIXTURES / path).exists() else REPO / path
    resp = client.post("/decks", files={"file": (full.name, full.read_bytes())})
    assert resp.status_code == 201, resp.text
    return resp.json()  # type: ignore[no-any-return]


def test_upload_list_and_get(client: TestClient) -> None:
    deck = upload(client, "artifact.html")
    assert deck["title"] == "Fixture artifact deck"
    assert len(deck["slides"]) == 4
    upload(client, "sample.pptx")
    assert [d["source"] for d in client.get("/decks").json()] == ["pptx", "html"]
    got = client.get(f"/decks/{deck['id']}").json()
    assert got["slides"][0]["notes"] == "Notes for the first slide."
    assert got["attachments"] == []
    assert client.get("/decks/999").status_code == 404


def test_ask_and_trace(client: TestClient) -> None:
    deck = upload(client, "decks/kettle-quarterly-review.pptx")
    csv = REPO / "decks" / "kettle-quarterly-review.data.csv"
    att = client.post(f"/decks/{deck['id']}/attachments", files={"file": (csv.name, csv.read_bytes())})
    assert att.status_code == 201 and att.json()["chunks"] == 1
    resp = client.post(
        f"/decks/{deck['id']}/slides/2/ask?wait=true", json={"question": "Why did the harbour cafe grow?"}
    )
    assert resp.status_code == 202 and resp.json()["status"] == "answered"
    body = resp.json()["answer"]
    assert body["agent"] == "slide-2"
    assert body["citations"][0] == {
        "block_id": "slide:2:body",
        "slide": 2,
        "attachment": None,
        "influence": None,
        "file": None,
    }
    trace = client.get(f"/traces/{body['trace_id']}").json()
    assert trace["agent"] == "slide-2" and trace["steps"][-1]["node"] == "persist"
    assert trace["steps"][0]["ms"] == 1.0
    assert client.get("/traces/999").status_code == 404


def test_errors(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    bad = client.post("/decks", files={"file": ("x.bin", b"\x00\x01")})
    assert bad.status_code == 422 and "unknown deck format" in bad.json()["detail"]
    deck = upload(client, "gslides.json")
    assert client.post(f"/decks/{deck['id']}/slides/9/ask", json={"question": "q"}).status_code == 404
    assert client.post("/decks/999/slides/1/ask", json={"question": "q"}).status_code == 404
    pdf = client.post(f"/decks/{deck['id']}/attachments", files={"file": ("a.pdf", b"%PDF")})
    assert pdf.status_code == 422
    monkeypatch.setattr(api, "MAX_UPLOAD_BYTES", 10)
    assert client.post("/decks", files={"file": ("a.html", b"<section>" * 5)}).status_code == 413


def test_default_store_and_provider(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("LECTERN_DB", str(tmp_path / "x.db"))
    client = TestClient(create_app())
    assert client.get("/decks").json() == []
    assert (tmp_path / "x.db").exists()
