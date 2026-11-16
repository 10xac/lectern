"""The DNA as a graph (for the visual view), as an ordered trace (the text view), and as search
blocks for the K researcher (weighted by degree).

Graph nodes: ``deck``, ``slide``, ``component``, ``influence``, ``file``, ``url``. Edges:
``shapes`` (influence → its target, weighted by degree), ``derived`` (influence → its parent),
``cites`` (influence → file or URL) and ``contains`` (deck → slide → component).
"""

from __future__ import annotations

from typing import Any

from lectern.dna import DNA, WEIGHT, Influence
from lectern.files import FileError
from lectern.graph.state import Block
from lectern.models import Deck
from lectern.search import bm25

ORDER = {"high": 0, "medium": 1, "low": 2, "general": 3}
LAYER = {"deck": 0, "influence": 1, "file": 1, "url": 1, "component": 2, "slide": 3}


def _node(nodes: dict[str, dict[str, Any]], node_id: str, node_type: str, label: str, **extra: Any) -> str:
    nodes.setdefault(
        node_id, {"id": node_id, "type": node_type, "label": label, "layer": LAYER[node_type], **extra}
    )
    return node_id


def graph(dna: DNA, deck: Deck, n: int | None = None) -> dict[str, Any]:
    """The DNA graph of slide ``n`` or (``None``) the whole deck. Deterministic order (golden-tested)."""
    influences = dna.list(deck.id or 0, slide=n)
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    root = _node(nodes, "deck", "deck", deck.title)
    slides = [s for s in deck.slides if n is None or s.n == n]
    for s in slides:
        edges.append(
            {
                "from": root,
                "to": _node(nodes, f"slide:{s.n}", "slide", f"{s.n}. {s.title}"),
                "type": "contains",
            }
        )
    for inf in sorted(influences, key=lambda i: (ORDER[i.degree], i.created_at, i.id)):
        stale = dna.stale(inf)
        me = _node(
            nodes,
            f"inf:{inf.id}",
            "influence",
            inf.title,
            kind=inf.kind,
            degree=inf.degree,
            author=inf.author.name,
            stale=bool(stale),
        )
        targets = (
            [root]
            if inf.scope.kind == "deck"
            else [f"slide:{m}" for m in inf.scope.slides if f"slide:{m}" in nodes]
        )
        if inf.target.component != "whole" and inf.scope.kind != "deck":
            targets = [component(nodes, edges, t, inf) for t in targets]
        for t in targets:
            edges.append(
                {"from": me, "to": t, "type": "shapes", "degree": inf.degree, "weight": WEIGHT[inf.degree]}
            )
        if inf.parent_id and f"inf:{inf.parent_id}" in nodes:
            edges.append({"from": me, "to": f"inf:{inf.parent_id}", "type": "derived"})
        for ref in inf.refs:
            edges.append({"from": me, "to": ref_node(dna, nodes, ref.model_dump()), "type": "cites"})
    # Within a layer, nodes keep insertion order: slides by number, influences strongest first.
    return {"nodes": sorted(nodes.values(), key=lambda x: x["layer"]), "edges": edges}


def component(
    nodes: dict[str, dict[str, Any]], edges: list[dict[str, Any]], slide: str, inf: Influence
) -> str:
    t = inf.target
    key = f"comp:{slide.split(':')[1]}:{t.component}:{t.element_id or ''}"
    if key not in nodes:
        _node(nodes, key, "component", t.label or t.element_id or t.component, component=t.component)
        edges.append({"from": key, "to": slide, "type": "contains"})
    return key


def ref_node(dna: DNA, nodes: dict[str, dict[str, Any]], ref: dict[str, Any]) -> str:
    if ref["type"] == "url":
        return _node(nodes, f"url:{ref['url']}", "url", ref.get("label") or ref["url"], url=ref["url"])
    try:
        file = dna.files.by_id(ref["file_id"])
        return _node(
            nodes,
            f"file:{file.id}",
            "file",
            ref.get("label") or file.path.rsplit("/", 1)[-1],
            path=file.path,
            mime=file.mime,
            status=file.status,
        )
    except FileError:
        return _node(nodes, f"file:{ref['file_id']}", "file", "(deleted file)", status="purged")


def text(dna: DNA, deck: Deck, n: int | None = None) -> str:
    """The ordered textual trace: strongest influence first."""
    influences = sorted(dna.list(deck.id or 0, slide=n), key=lambda i: (ORDER[i.degree], i.created_at, i.id))
    slide = deck.slide(n) if n is not None else None
    head = f"Slide {n} ({slide.title})" if slide else f"The deck “{deck.title}”"
    if not influences:
        return f"{head} has no recorded DNA yet."
    lines = [f"{head} was shaped by:"]
    for inf in influences:
        on = "" if inf.target.component == "whole" else f" on its {inf.target.label or inf.target.component}"
        plural = "s" if len(inf.scope.slides) > 1 else ""
        numbers = ", ".join(map(str, inf.scope.slides))
        scope = "the whole deck" if inf.scope.kind == "deck" else f"slide{plural} {numbers}"
        who = inf.author.name + (f" ({inf.author.model})" if inf.author.model else "")
        line = f"- ({inf.degree}) {inf.title}{on}: {inf.kind} by {who}, for {scope} [dna:{inf.id}]"
        refs = [r.label or r.url or dna_file_label(dna, r.file_id) for r in inf.refs]
        if refs:
            line += "; refs: " + "; ".join(refs)
        for file_id, (then, now) in dna.stale(inf).items():
            line += f" ⚠ written for v{then} of {dna_file_label(dna, file_id)}, now v{now}"
        lines.append(line)
    return "\n".join(lines)


def dna_file_label(dna: DNA, file_id: str | None) -> str:
    try:
        return dna.files.by_id(file_id or "").path
    except FileError:
        return "(deleted file)"


def search_blocks(dna: DNA, deck: Deck, n: int | None, question: str, k: int = 4) -> list[Block]:
    """DNA text and referenced file pages that match the question, weighted by degree."""
    docs: list[tuple[Block, float]] = []
    for inf in dna.list(deck.id or 0, slide=n):
        weight = WEIGHT[inf.degree]
        docs.append((Block(f"dna:{inf.id}", f"{inf.title}\n{inf.body}"), weight))
        for ref in inf.refs:
            if ref.file_id:
                pages = dna.files.text(ref.file_id).split("\f")
                docs += [
                    (Block(f"file:{ref.file_id}:p{i}", p), weight)
                    for i, p in enumerate(pages, 1)
                    if p.strip()
                ]
    if not docs:
        return []
    scores = bm25(question, [b.text for b, _ in docs])
    ranked = sorted(range(len(docs)), key=lambda i: (-scores[i] * docs[i][1], i))
    seen: set[str] = set()
    out = []
    for i in ranked:
        block = docs[i][0]
        if scores[i] > 0 and block.id not in seen:
            seen.add(block.id)
            out.append(block)
    return out[:k]
