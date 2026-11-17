"""Managing decks and slides (decision D15): parity over REST and MCP, DNA and chats that follow their
slide, a deck delete that leaves nothing behind, and uploads that are all or nothing."""

from __future__ import annotations

import io
from typing import Any

from conftest import REPO
from fastapi.testclient import TestClient
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt

from lectern.api import create_app
from lectern.blobs import MemoryBlobs
from lectern.providers.fake import FakeProvider
from lectern.store import Store

NOTE = {"kind": "note", "degree": "low", "title": "about the ferry"}


def app(**kw: Any) -> TestClient:
    return TestClient(create_app(Store(), FakeProvider(), **kw))


def kettle(c: TestClient) -> int:
    pptx = (REPO / "decks" / "kettle-quarterly-review.pptx").read_bytes()
    return int(c.post("/decks", files={"file": ("k.pptx", pptx)}).json()["id"])


def titles(c: TestClient, d: int) -> list[str]:
    return [s["title"] for s in c.get(f"/decks/{d}").json()["slides"]]


def test_uploaded_decks_keep_dna_and_chats_on_their_slide_when_slides_move() -> None:
    with app() as c:
        d = kettle(c)
        before = titles(c, d)
        c.post(f"/decks/{d}/influences", json=NOTE | {"scope": {"kind": "slide", "slides": [3]}})
        c.post(f"/decks/{d}/slides/3/ask?wait=true", json={"question": "Why did the harbour cafe grow?"})
        assert c.delete(f"/decks/{d}/slides/1").status_code == 200
        assert titles(c, d) == before[1:]
        moved = c.post(f"/decks/{d}/slides/2/move", json={"to": 1}).json()
        assert moved["slides"][0]["title"] == before[2]
        assert [i["title"] for i in c.get(f"/decks/{d}/influences?slide=1").json()] == ["about the ferry"]
        assert [m["role"] for m in c.get(f"/decks/{d}/slides/1/messages").json()] == ["user", "agent"]
        assert c.get(f"/decks/{d}/slides/2/messages").json() == []
        new = c.post(f"/decks/{d}/slides", json={"at": 1, "title": "Agenda", "body": "One\nTwo"}).json()
        assert new["n"] == 1 and titles(c, d)[:2] == ["Agenda", before[2]]
        copy = c.post(f"/decks/{d}/slides/1/duplicate").json()
        assert copy["n"] == 2 and copy["ref"] != new["ref"]
        assert titles(c, d)[:3] == ["Agenda", "Agenda", before[2]]
        markup = "<section><h1>Plan</h1><p>Ship it</p></section>"
        html = c.patch(f"/decks/{d}/slides/2", json={"html": markup}).json()
        assert html["title"] == "Plan" and html["body"] == "Ship it"
        assert c.patch(f"/decks/{d}/slides/2", json={"html": ""}).json()["html"] is None
        assert [i["title"] for i in c.get(f"/decks/{d}/influences?slide=3").json()] == ["about the ferry"]


def test_folder_decks_change_their_files() -> None:
    with app() as c:
        d = c.put("/slides?path=decks/t/01.md", content=b"# One\nBody").json()["deck_id"]
        c.put("/slides?path=decks/t/02.html", content=b"<section><h1>Two</h1></section>")
        c.post(f"/decks/{d}/slides/2/move", json={"to": 1})
        assert titles(c, d) == ["Two", "One"]
        c.post(f"/decks/{d}/slides/2/duplicate")
        c.post(f"/decks/{d}/slides", json={"title": "Last", "body": "end"})
        assert titles(c, d) == ["Two", "One", "One", "Last"]
        c.patch(f"/decks/{d}/slides/2", json={"body": "New body"})
        files = c.app.state.hub.files  # type: ignore[attr-defined]
        assert files.read("decks/t/01.md")[1].decode().strip() == "# One\n\nNew body"
        c.delete(f"/decks/{d}/slides/3")
        assert titles(c, d) == ["Two", "One", "Last"]
        assert [f["path"].split("/")[-1][:6] for f in c.get("/files?prefix=decks/t/").json()] == [
            "01.md",
            "02.htm",
            "slide-",
        ]


def test_deleting_a_deck_removes_everything_in_it() -> None:
    blobs = MemoryBlobs()
    with app(blobs=blobs) as c:
        d = kettle(c)
        c.post(f"/decks/{d}/influences", json=NOTE | {"scope": {"kind": "deck"}})
        c.post(f"/decks/{d}/slides/2/ask?wait=true", json={"question": "Why did the harbour cafe grow?"})
        assert c.patch(f"/decks/{d}", json={"title": "Renamed"}).json()["title"] == "Renamed"
        assert c.get(f"/decks/{d}/original").content[:2] == b"PK"  # the .pptx as uploaded
        assert blobs.keys() != []
        assert c.delete(f"/decks/{d}").status_code == 204
        assert c.get(f"/decks/{d}").status_code == 404 and c.get("/decks").json() == []
        assert blobs.keys() == [] and c.get("/files").json() == []
        hub = c.app.state.hub  # type: ignore[attr-defined]
        with hub.store.tx() as db:
            for table in ("slides", "influences", "slide_messages", "jobs", "traces", "files"):
                assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0, table


class ReadOnly(MemoryBlobs):
    def put(self, key: str, data: bytes) -> None:
        raise PermissionError(13, "Permission denied", key)


def test_unwritable_storage_is_loud_and_leaves_no_empty_deck() -> None:
    with app(blobs=ReadOnly()) as c:
        health = c.get("/health").json()
        assert health["status"] == "degraded" and "Permission denied" in health["storage"]
        pptx = (REPO / "decks" / "kettle-quarterly-review.pptx").read_bytes()
        refused = c.post("/decks", files={"file": ("k.pptx", pptx)})
        assert refused.status_code == 503 and "not writable" in refused.json()["detail"]
        assert c.put("/slides?path=decks/x/01.md", content=b"# One").status_code == 503
        assert c.get("/decks").json() == []


def picture_deck() -> bytes:
    png = io.BytesIO()
    Image.new("RGB", (40, 20), "#cc3300").save(png, "PNG")
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[5])
    slide.shapes.title.text = "Revenue"
    slide.shapes.add_picture(io.BytesIO(png.getvalue()), Inches(1), Inches(2), Inches(2), Inches(1))
    box = slide.shapes.add_textbox(Inches(4), Inches(2), Inches(4), Inches(1))
    box.text_frame.text = "Up 12%"
    box.text_frame.paragraphs[0].runs[0].font.size = Pt(24)
    out = io.BytesIO()
    prs.save(out)
    return out.getvalue()


def test_powerpoint_slides_are_drawn_with_their_pictures() -> None:
    with app() as c:
        deck = c.post("/decks", files={"file": ("p.pptx", picture_deck())}).json()
        html = deck["slides"][0]["html"]
        assert 'class="pptx-slide"' in html and "Up 12%" in html and "font-size:32.0px" in html
        src = html.split('<img src="', 1)[1].split('"', 1)[0]
        assert src.startswith(f"/media/{deck['id']}/")
        assert c.get(src).headers["content-type"] == "image/png"
        assert c.get(f"/media/{deck['id']}/../../etc.png").status_code == 404
