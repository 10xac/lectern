"""The v0.2 demo: an AI client builds the "Knowing where not to look" deck through MCP, logs its
conceptual DNA as it goes, then asks three slides questions in parallel.

    uv run python scripts/demo.py            # or: make demo

It runs offline with no keys (the fake model, rules triage, no web). With keys in the environment
(``LECTERN_PROVIDER``/``LECTERN_API_KEY``/``LECTERN_MODEL``, ``EXA_API_KEY``, ``OPENROUTER_API_KEY``)
the same script uses the real model, the web and jev triage. The database and files go to
``$LECTERN_DB`` and ``$LECTERN_BLOBS`` (defaults: ``demo.db`` and ``demo-blobs``), so the web app can
show the result afterwards: ``DB=demo.db LECTERN_BLOBS=demo-blobs make dev``.
"""

from __future__ import annotations

import asyncio
import base64
import os
import sys
from pathlib import Path
from typing import Any

from mcp import Client
from mcp.types import Implementation

from lectern import mcp_server
from lectern.api import build_hub
from lectern.blobs import blobs_from_env
from lectern.store import Store

ROOT = Path(__file__).resolve().parent.parent
DECK = ROOT / "decks" / "knowing-where-not-to-look"
FOLDER = "decks/knowing-where-not-to-look"
AI = {"name": "lectern demo (a scripted AI client)", "version": "0.2"}


def slide(n: int, kind: str, degree: str, title: str, body: str, **extra: Any) -> dict[str, Any]:
    scope = {"kind": "slide", "slides": [n]} if n else {"kind": "deck"}
    return {"scope": scope, "kind": kind, "degree": degree, "title": title, "body": body} | extra


DNA = [
    slide(
        0,
        "idea",
        "general",
        "Write for a mixed room",
        "No prior NLP is assumed: every symbol is said in words first, and each slide makes one claim.",
    ),
    slide(
        1,
        "idea",
        "high",
        "Lead with the thesis, not the method",
        "The talk opens on the sentence the note is built around: an agent is only as good as its sense "
        "of where not to look.",
    ),
    slide(
        2,
        "reasoning",
        "high",
        "Four sources, because each fails differently",
        "The note splits knowledge into P, W, K and M. A table makes the failure modes easy to compare.",
        target={"component": "element", "element_id": "table-1", "label": "sources table"},
    ),
    slide(
        2,
        "note",
        "medium",
        "Users' turns belong in W",
        "We cannot estimate how much the user knows, so their turns are treated like the open web.",
    ),
    slide(
        3,
        "reasoning",
        "high",
        "Hurdle, rare passage, ghost passage",
        "Three different masses of uncertainty, each with a different right move: decline, look on purpose, "
        "or stop and derive, ask or abstain.",
    ),
    slide(
        4,
        "explanation",
        "high",
        "Agreement converges to the proposal, not the target",
        "Sample agreement estimates Q(y|q), the agent's habits. It equals correctness only when the proposal "
        "matches the target.",
        target={"component": "element", "element_id": "figure-1", "label": "proposal vs target figure"},
    ),
    slide(
        5,
        "reasoning",
        "high",
        "Ghost mass is reduced only by another source",
        "More samples from the same source cannot find an answer its corpus does not hold.",
    ),
    slide(
        6,
        "idea",
        "medium",
        "End on the decision rule",
        "Answer, qualify, ask, abstain: the four outcomes the confidence chips show in lectern.",
    ),
]
QUESTIONS = [
    (2, "Which source is reliable but narrow?"),
    (5, "What is ghost mass and what reduces it?"),
    (6, "Who won the 1987 Dubai chess olympiad?"),
]


async def call(c: Client, tool: str, **args: Any) -> Any:
    result = await c.call_tool(tool, args)
    if result.is_error:
        raise RuntimeError(f"{tool}: {result.content}")
    data = result.structured_content or {}
    return data.get("result", data) if set(data) == {"result"} else data


async def build_deck(c: Client) -> int:
    """put_slide for each file, then the DNA in one batch, citing the note's summary."""
    for path in sorted(DECK.glob("*.html")):
        put = await call(c, "put_slide", path=f"{FOLDER}/{path.name}", content=path.read_text())
    deck_id = int(put["deck_id"])
    if await call(c, "list_influences", deck_id=deck_id):  # safe to re-run: the DNA is logged once
        print(f"deck {deck_id}: already built; slides refreshed, DNA kept")
        return deck_id
    summary = base64.b64encode((DECK / "refs" / "note-summary.md").read_bytes()).decode()
    ref = await call(c, "upload_file", deck_id=deck_id, name="note-summary.md", content_base64=summary)
    cite = [{"type": "file", "file_id": ref["id"], "label": "the note (summary)"}]
    items = [item | {"refs": cite} if item["degree"] == "high" else item for item in DNA]
    logged = await call(
        c, "add_influences", deck_id=deck_id, influences=items, model=os.environ.get("LECTERN_MODEL")
    )
    print(f"deck {deck_id}: {len(DNA)} DNA records logged over MCP by {logged[0]['author']['name']}")
    return deck_id


async def ask_in_parallel(c: Client, deck_id: int) -> None:
    jobs = {
        n: (q, (await call(c, "ask", deck_id=deck_id, slide=n, question=q))["job_id"]) for n, q in QUESTIONS
    }
    done: dict[int, Any] = {}
    while len(done) < len(jobs):
        for n, (_, job_id) in jobs.items():
            job = await call(c, "get_job", job_id=job_id)
            if job["status"] not in ("queued", "triaging", "researching", "fusing"):
                done[n] = job
        await asyncio.sleep(0.05)
    for n, (question, _) in jobs.items():
        job = done[n]
        conf = (job.get("answer") or {}).get("confidence") or {}
        sources = ", ".join(f"{s['source']}:{s['status']}" for s in conf.get("sources", []))
        verdict = f"{job['status']} ({conf.get('verdict')}; {conf.get('why')})"
        print(f"\nslide {n} · {question}\n  {verdict} [{sources}]")
        print("  " + (job.get("answer") or {}).get("answer", job.get("error") or "")[:300])


async def main() -> int:
    store = Store(os.environ.get("LECTERN_DB", "demo.db"))
    blobs = blobs_from_env({"LECTERN_BLOBS": os.environ.get("LECTERN_BLOBS", "demo-blobs")})
    server = mcp_server.build(build_hub(store, blobs=blobs))
    async with Client(server, client_info=Implementation(**AI)) as c:
        deck_id = await build_deck(c)
        print("\n" + (await call(c, "get_dna", deck_id=deck_id, slide=2))["text"])
        await ask_in_parallel(c, deck_id)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
