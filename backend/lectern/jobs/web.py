"""The W researcher: Exa search, plus ``fetch_url`` when a hit came back without text.

Its reliability ``r`` starts from a prior and moves with agreement among the top snippets: when
the other results share the answer's terms, the web agrees with itself.
"""

from __future__ import annotations

from lectern.graph.state import Block
from lectern.jobs.research import RESEARCHERS, Context, Found, ToolCalls, answer_from, terms
from lectern.models import SourceReport

EXA_URL = "https://api.exa.ai/search"
RESULTS = 4
SNIPPET_CHARS = 1200
TIMEOUT_S = 15.0
R_PRIOR, R_SPAN = 0.4, 0.4


def agreement(answer: str, snippets: list[str]) -> float:
    """The share of snippets that have at least two of the answer's content terms."""
    words = terms(answer)
    if not snippets or not words:
        return 0.0
    return sum(1 for s in snippets if len(words & terms(s)) >= 2) / len(snippets)


def research_w(ctx: Context, calls: ToolCalls) -> Found:
    calls.take()  # web_search
    body = {"query": ctx.question, "numResults": RESULTS, "contents": {"text": True}}
    data = ctx.http.post_json(EXA_URL, body, {"x-api-key": ctx.env.get("EXA_API_KEY", "")}, TIMEOUT_S)
    blocks: list[Block] = []
    used = 1
    for i, hit in enumerate(data.get("results", [])[:RESULTS]):
        text, url = str(hit.get("text") or ""), str(hit.get("url") or "")
        if not text and url and i == 0:
            calls.take()  # fetch_url
            used += 1
            text = ctx.http.get_text(url, TIMEOUT_S)
        if text:
            title = str(hit.get("title") or url)
            blocks.append(Block(f"web:{i + 1}", f"{title} ({url})\n{text[:SNIPPET_CHARS]}"))
    answer = answer_from(ctx, blocks)
    r = R_PRIOR + R_SPAN * agreement(answer, [b.text for b in blocks])
    report = SourceReport(
        source="W",
        status="done",
        reason="" if blocks else "no results",
        answer=answer,
        r=round(r, 3),
        g=0.3 if blocks else 0.9,
        block_ids=[b.id for b in blocks],
        tool_calls=used,
    )
    return report, blocks


RESEARCHERS["W"] = research_w
