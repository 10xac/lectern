"""AC-P4: the MCP tools are listed and round-trip with the SDK's in-memory client, at parity with REST."""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from mcp import Client
from mcp.types import Implementation
from pdf import tiny_pdf

from lectern import cli, mcp_server
from lectern.api import build_hub, create_app
from lectern.providers.fake import FakeProvider
from lectern.store import Store

EXPECTED = {
    "list_decks",
    "get_deck",
    "get_slide",
    "create_deck",
    "add_influence",
    "add_influences",
    "update_influence",
    "remove_influence",
    "list_influences",
    "upload_file",
    "add_reference",
    "get_dna",
    "ask",
    "get_job",
    "put_slide",
    "read_slide",
    "update_slide_meta",
    "put_file",
    "read_file",
    "list_files",
    "move_file",
    "delete_file",
    "reconcile_files",
    "relink_file",
}


async def call(c: Client, tool: str, **args: Any) -> Any:
    result = await c.call_tool(tool, args)
    assert not result.is_error, (tool, result.content)
    data = result.structured_content
    return data.get("result", data) if isinstance(data, dict) and set(data) == {"result"} else data


async def slides_and_dna(c: Client) -> tuple[int, dict[str, Any]]:
    """Stage one: build a two-slide deck and log its DNA, as an AI tool would while writing it."""
    assert {t.name for t in (await c.list_tools()).tools} == EXPECTED
    await call(c, "put_slide", path="decks/talk/01-why.md", content="# Why\nKnowing where not to look.")
    put = await call(c, "put_slide", path="decks/talk/02-how.html", content="<h1>How</h1><img src='a.png'>")
    deck_id = put["deck_id"]
    assert put["slide"]["elements"] == [{"id": "h1-1", "tag": "h1"}, {"id": "img-1", "tag": "img"}]
    one = {
        "scope": {"kind": "slide", "slides": [2]},
        "kind": "reasoning",
        "degree": "high",
        "title": "Triage before search",
        "target": {"component": "image", "element_id": "img-1"},
    }
    added = await call(c, "add_influence", deck_id=deck_id, influence=one, model="claude-opus-5-5")
    assert added["via"] == "mcp" and added["author"] == {
        "type": "ai",
        "name": "Claude Code",
        "tool": "Claude Code",
        "model": "claude-opus-5-5",
    }
    batch = [
        one | {"title": "Deck voice", "scope": {"kind": "deck"}, "degree": "general"},
        one | {"title": "Both slides", "scope": {"kind": "slides", "slides": [1, 2]}, "degree": "low"},
    ]
    assert len(await call(c, "add_influences", deck_id=deck_id, influences=batch)) == 2
    pdf = base64.b64encode(tiny_pdf("The note defines ghost mass g for each source.")).decode()
    ref = await call(c, "upload_file", deck_id=deck_id, name="note.pdf", content_base64=pdf)
    cited = await call(
        c,
        "add_reference",
        deck_id=deck_id,
        influence_id=added["id"],
        ref={"type": "file", "file_id": ref["id"], "label": "the note"},
    )
    assert cited["refs"][0]["file_id"] == ref["id"]
    text = (await call(c, "get_dna", deck_id=deck_id, slide=2))["text"]
    assert "(high) Triage before search on its image: reasoning by Claude Code (claude-opus-5-5)" in text
    graph = await call(c, "get_dna", deck_id=deck_id, format="graph")
    assert {n["type"] for n in graph["nodes"]} >= {"deck", "slide", "influence", "component", "file"}
    return deck_id, added


async def files_and_jobs(c: Client, deck_id: int, added: dict[str, Any]) -> None:
    """Stage two: read and reorder slides, move a file, ask a question and read a refused call."""
    read = await call(c, "read_slide", path="decks/talk/02-how.html")
    assert read["n"] == 2 and "Triage before search" in read["dna"]
    await call(c, "update_slide_meta", path="decks/talk/02-how.html", meta={"order": 0})
    assert (await call(c, "get_slide", deck_id=deck_id, n=1))["title"] == "How"  # reordered, DNA follows
    assert "Triage before search" in (await call(c, "get_slide", deck_id=deck_id, n=1))["text"]
    moved = await call(c, "move_file", src="decks/talk/01-why.md", dst="decks/talk/09-why.md")
    assert (await call(c, "read_file", path=moved["path"]))["text"].startswith("# Why")
    job = await call(
        c, "ask", deck_id=deck_id, slide=1, question="What does the note define for each source?"
    )
    for _ in range(200):
        got = await call(c, "get_job", job_id=job["job_id"])
        if got["status"] not in ("queued", "triaging", "researching", "fusing"):
            break
        await asyncio.sleep(0.01)
    assert got["status"] == "answered", got
    assert any(x["block_id"].startswith(("file:", "dna:")) for x in got["answer"]["citations"])
    bad = await c.call_tool("get_slide", {"deck_id": 99, "n": 1})
    assert bad.is_error and "no deck 99" in bad.content[0].text  # type: ignore[union-attr]
    assert (await call(c, "list_decks"))[0]["source"] == "folder"


def test_tools_round_trip_with_the_in_memory_client() -> None:
    server = mcp_server.build(build_hub(Store(), FakeProvider()))

    async def go() -> None:
        async with Client(server, client_info=Implementation(name="Claude Code", version="1")) as c:
            assert {t.name for t in (await c.list_tools()).tools} == EXPECTED
            await files_and_jobs(c, *await slides_and_dna(c))

    asyncio.run(go())


def test_mcp_and_rest_rows_have_the_same_shape() -> None:
    with TestClient(create_app(Store(), FakeProvider())) as client:
        put = client.put("/slides?path=decks/a/01.md", content=b"# One").json()
        body = {"scope": {"kind": "slide", "slides": [1]}, "kind": "note", "degree": "low", "title": "t"}
        rest = client.post(f"/decks/{put['deck_id']}/influences", json=body).json()
        hub = client.app.state.hub  # type: ignore[attr-defined]

        async def go() -> Any:
            async with Client(mcp_server.build(hub)) as c:
                return await call(c, "add_influence", deck_id=put["deck_id"], influence=body)

        via_mcp = asyncio.run(go())
        assert set(via_mcp) == set(rest) and via_mcp["via"] == "mcp" and rest["via"] == "api"


def test_http_mount_needs_a_personal_token_when_login_is_on(monkeypatch: pytest.MonkeyPatch) -> None:
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
    headers = {"Accept": "application/json, text/event-stream"}
    # The SDK refuses unknown Host headers (DNS-rebinding protection), so talk to it as localhost.
    with TestClient(create_app(Store(), FakeProvider()), base_url="http://127.0.0.1:8000") as client:
        assert client.post("/mcp/", json=init, headers=headers).status_code == 200  # login off: open locally
    monkeypatch.setenv("LECTERN_AUTH", "1")
    with TestClient(create_app(Store(), FakeProvider()), base_url="http://127.0.0.1:8000") as client:
        users = client.app.state.hub.users  # type: ignore[attr-defined]
        user, invite = users.invite("ai@example.org")
        users.accept(invite, "a long enough password")
        token, secret = users.create_token(user.id, "laptop", 30)
        assert client.post("/mcp/", json=init, headers=headers).status_code == 401
        wrong = headers | {"Authorization": "Bearer lectern_pat_nope"}
        assert client.post("/mcp/", json=init, headers=wrong).status_code == 401
        ok = headers | {"Authorization": f"Bearer {secret}"}
        assert client.post("/mcp/", json=init, headers=ok).status_code == 200
        assert users.tokens(user.id)[0]["last_used_at"] is not None
        users.revoke_token(user.id, token["id"])
        assert client.post("/mcp/", json=init, headers=ok).status_code == 401


def test_cli_dna_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LECTERN_DB", str(tmp_path / "x.db"))
    monkeypatch.setenv("LECTERN_BLOBS", str(tmp_path / "blobs"))
    slide = tmp_path / "s.md"
    slide.write_text("# Intro\nHello")
    assert cli.main(["put-slide", "decks/cli/01.md", str(slide)]) == 0
    deck_id = json.loads(capsys.readouterr().out)["deck_id"]
    inf = tmp_path / "i.json"
    inf.write_text(
        json.dumps({"scope": {"kind": "deck"}, "kind": "idea", "degree": "general", "title": "Start small"})
    )
    assert cli.main(["add-influence", str(deck_id), str(inf)]) == 0
    assert json.loads(capsys.readouterr().out)[0]["via"] == "cli"
    assert cli.main(["dna", str(deck_id), "--slide", "1"]) == 0
    assert "(general) Start small" in capsys.readouterr().out
    assert cli.main(["reconcile"]) == 0
    assert json.loads(capsys.readouterr().out)["missing"] == []
    assert (tmp_path / "blobs" / "decks" / "cli" / "01.md").exists()
    inf.write_text(
        json.dumps({"scope": {"kind": "slide", "slides": [7]}, "kind": "idea", "degree": "low", "title": "x"})
    )
    assert cli.main(["add-influence", str(deck_id), str(inf)]) == 2
