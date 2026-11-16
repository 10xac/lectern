"""AC-P3: the DNA model, references, REST, the graph and the textual trace."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any

import pytest
from conftest import FIXTURES, REPO
from fastapi.testclient import TestClient
from pdf import tiny_pdf

from lectern.api import create_app
from lectern.providers.fake import FakeProvider
from lectern.store import Store

GOLDEN = FIXTURES.parent / "dna_graph.json"


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(Store(), FakeProvider(), clock=lambda: 1.0)) as c:
        yield c


@pytest.fixture
def deck_id(client: TestClient) -> int:
    pptx = (REPO / "decks" / "kettle-quarterly-review.pptx").read_bytes()
    return int(client.post("/decks", files={"file": ("kettle.pptx", pptx)}).json()["id"])


def influence(slides: list[int] | None, title: str, degree: str = "high", **extra: Any) -> dict[str, Any]:
    scope = (
        {"kind": "deck"}
        if slides is None
        else {"kind": "slide" if len(slides) == 1 else "slides", "slides": slides}
    )
    return {"scope": scope, "kind": "reasoning", "degree": degree, "title": title} | extra


def test_ui_rest_and_batch_give_the_same_row_shape(client: TestClient, deck_id: int) -> None:
    ui = client.post(f"/decks/{deck_id}/influences?via=ui", json=influence([2], "Board memo"))
    api = client.post(f"/decks/{deck_id}/influences", json=influence([2], "Board memo"))
    batch = client.post(
        f"/decks/{deck_id}/influences/batch", json=[influence([3], "x"), influence(None, "y")]
    )
    assert ui.status_code == api.status_code == batch.status_code == 201
    shapes = {frozenset(r) for r in (ui.json(), api.json(), *batch.json())}
    assert len(shapes) == 1 and ui.json()["via"] == "ui" and api.json()["via"] == "api"
    assert ui.json()["slide_ids"][0].endswith("#2")  # uploaded deck: <file id>#<n>
    bad = client.post(f"/decks/{deck_id}/influences/batch", json=[influence([3], "ok"), influence([9], "no")])
    assert (
        bad.status_code == 422 and len(client.get(f"/decks/{deck_id}/influences").json()) == 4
    )  # all or nothing
    assert (
        client.post(f"/decks/{deck_id}/influences", json=influence([2], "x", colour="red")).status_code == 422
    )


def test_a_subset_scope_shows_on_exactly_those_slides(client: TestClient, deck_id: int) -> None:
    client.post(f"/decks/{deck_id}/influences", json=influence([2, 4], "Regional story", "medium"))
    client.post(f"/decks/{deck_id}/influences", json=influence(None, "House style", "general"))
    for n, expected in (
        (1, ["House style"]),
        (2, ["Regional story", "House style"]),
        (3, ["House style"]),
        (4, ["Regional story", "House style"]),
    ):
        got = client.get(f"/decks/{deck_id}/influences?slide={n}").json()
        assert [i["title"] for i in got] == expected, n
        nodes = client.get(f"/decks/{deck_id}/slides/{n}/dna").json()["nodes"]
        assert sorted(x["label"] for x in nodes if x["type"] == "influence") == sorted(expected)
    assert [i["title"] for i in client.get(f"/decks/{deck_id}/influences?degree=general").json()] == [
        "House style"
    ]


def test_a_pdf_reference_is_searchable_in_k_and_cited(client: TestClient, deck_id: int) -> None:
    pdf = tiny_pdf("The board memo approved a lighthouse kiosk budget of 90k for the harbour.")
    ref = client.post(
        f"/decks/{deck_id}/files", files={"file": ("board-memo.pdf", pdf, "application/pdf")}
    ).json()
    assert ref["mime"] == "application/pdf" and ref["path"] == f"refs/{deck_id}/board-memo.pdf"
    body = influence(
        [5],
        "Q4 plan follows the board memo",
        refs=[{"type": "file", "file_id": ref["id"], "label": "memo p.1"}],
    )
    added = client.post(f"/decks/{deck_id}/influences", json=body).json()
    job = client.post(
        f"/decks/{deck_id}/slides/5/ask?wait=true",
        json={"question": "What budget did the lighthouse kiosk get?"},
    ).json()
    ids = [c["block_id"] for c in job["answer"]["citations"]]
    assert f"file:{ref['id']}:p1" in ids, job["answer"]
    chip = next(c for c in job["answer"]["citations"] if c["block_id"].startswith("file:"))
    assert chip["file"] == ref["id"]
    k = next(s for s in job["sources"] if s["source"] == "K")
    assert f"dna:{added['id']}" in k["block_ids"] or f"file:{ref['id']}:p1" in k["block_ids"]


def test_degree_weights_change_retrieval_order(client: TestClient, deck_id: int) -> None:
    from lectern.dna.graph import search_blocks

    low = client.post(
        f"/decks/{deck_id}/influences", json=influence([2], "Espresso pricing idea", "low")
    ).json()
    high = client.post(
        f"/decks/{deck_id}/influences", json=influence([2], "Espresso pricing reasoning", "high")
    ).json()
    hub = client.app.state.hub  # type: ignore[attr-defined]
    order = [b.id for b in search_blocks(hub.dna, hub.deck(deck_id), 2, "espresso pricing")]
    assert order == [f"dna:{high['id']}", f"dna:{low['id']}"]
    client.patch(f"/decks/{deck_id}/influences/{low['id']}", json={"degree": "high"})
    client.patch(f"/decks/{deck_id}/influences/{high['id']}", json={"degree": "general"})
    order = [b.id for b in search_blocks(hub.dna, hub.deck(deck_id), 2, "espresso pricing")]
    assert order == [f"dna:{low['id']}", f"dna:{high['id']}"]
    history = client.get(f"/decks/{deck_id}/influences/{low['id']}/history").json()
    assert history[0]["data"]["degree"] == "low"  # every edit keeps the previous version


def test_dna_graph_matches_the_golden_file_and_text_trace(client: TestClient) -> None:
    put = client.put("/slides?path=decks/demo/01-chart.html", content=b"<h1>Revenue</h1><img src='c.png'>")
    deck_id = put.json()["deck_id"]
    client.put("/slides?path=decks/demo/02-next.md", content=b"# Next\nPlan")
    general = client.post(
        f"/decks/{deck_id}/influences", json=influence(None, "Plain-English style", "general")
    ).json()
    chart = influence(
        [1],
        "Q3 board memo",
        target={"component": "chart", "element_id": "img-1", "label": "revenue chart"},
        refs=[{"type": "url", "url": "https://example.org/memo", "label": "memo"}],
        author={"type": "ai", "name": "Claude", "model": "claude-opus-5-5"},
    )
    child = client.post(f"/decks/{deck_id}/influences", json=chart).json()
    client.post(
        f"/decks/{deck_id}/influences", json=influence([1, 2], "Follow-up", "low", parent_id=child["id"])
    )
    graph = client.get(f"/decks/{deck_id}/dna").json()
    ids = {general["id"]: "G", child["id"]: "C"}
    text = json.dumps(graph, sort_keys=True, indent=1)
    for real, fake in ids.items():
        text = text.replace(real, fake)
    for node in graph["nodes"]:
        if node["type"] == "influence" and node["id"][4:] not in ids:
            text = text.replace(node["id"][4:], "F")
    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.write_text(text + "\n")
    assert text + "\n" == GOLDEN.read_text()
    trace = client.get(f"/decks/{deck_id}/slides/1/dna?format=text").json()["text"]
    lines = trace.splitlines()
    assert lines[0] == "Slide 1 (Revenue) was shaped by:"
    assert lines[1].startswith(
        "- (high) Q3 board memo on its revenue chart: reasoning by Claude (claude-opus-5-5)"
    )
    assert lines[-1].startswith("- (general) Plain-English style")
    client.put("/slides?path=decks/demo/01-chart.html&mode=overwrite", content=b"<h1>Revenue v2</h1>")
    stale = client.get(f"/decks/{deck_id}/slides/1/dna?format=text").json()["text"]
    assert "⚠ written for v1 of decks/demo/01-chart.html, now v2" in stale


def test_file_and_slide_routes(client: TestClient) -> None:
    created = client.put("/slides?path=decks/x/01.md&mode=create", content=b"# One\nBody").json()
    assert created["slide"]["path"] == "decks/x/01.md" and created["slide"]["title"] == "One"
    assert client.put("/slides?path=decks/x/01.md&mode=create", content=b"# Again").status_code == 409
    read = client.get("/slides?path=decks/x/01.md").json()
    assert read["content"].startswith("# One") and read["n"] == 1 and "no recorded DNA" in read["dna"]
    assert client.patch("/file/meta?path=decks/x/01.md", json={"title": "First"}).json()["meta"] == {
        "title": "First"
    }
    assert client.get(f"/decks/{created['deck_id']}").json()["slides"][0]["title"] == "First"
    moved = client.post("/file/move", json={"src": "decks/x/01.md", "dst": "decks/x/01-first.md"}).json()
    assert (
        moved["id"] == created["file"]["id"]
        and client.get("/file?path=decks/x/01-first.md").json()["version"] == 1
    )
    assert client.get("/file/content?path=decks/x/01-first.md").content.startswith(b"# One")
    assert client.put("/file/content?path=notes/a.txt", content=b"hello").json()["mime"] == "text/plain"
    assert [f["path"] for f in client.get("/files?prefix=notes/").json()] == ["notes/a.txt"]
    gone = client.delete("/file?path=notes/a.txt").json()
    assert gone["status"] == "missing"
    rec = client.post("/files/reconcile").json()
    assert [f["id"] for f in rec["missing"]] == [gone["id"]]
    client.put("/file/content?path=notes/b.txt", content=b"other")
    assert client.post(f"/files/{gone['id']}/relink", json={"path": "notes/b.txt"}).status_code == 409
    assert client.delete(f"/files/{gone['id']}").status_code == 204
    assert client.get("/file?path=../etc").status_code == 422
    assert client.get("/file?path=nope.txt").status_code == 404
    assert client.put("/slides?path=loose.md", content=b"# x").status_code == 422
    assert client.get("/decks/999/dna").status_code == 404
