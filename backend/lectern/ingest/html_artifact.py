"""Claude artifact decks (HTML) → slides with presenter notes.

A slide is a ``<section>`` or any element with class ``slide``. A slide that contains other
slides is a group (reveal.js vertical slides): its children are flattened in document order and
the group itself is not a slide. Notes come from ``<aside class="notes">`` (the reveal.js
convention) or a ``data-notes`` attribute. The slide's own markup, without its notes, is kept
for display in a sandboxed iframe. Parsing uses only the stdlib ``html.parser``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html import escape
from html.parser import HTMLParser
from pathlib import PurePath
from typing import Any

from lectern.models import Deck, IngestError, Slide

VOID = frozenset("area base br col embed hr img input link meta source track wbr".split())
HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")
SKIP_TEXT = frozenset({"script", "style", "template"})


@dataclass
class Node:
    """A tiny DOM element: enough to find slides and serialise them back."""

    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[Node | str] = field(default_factory=list)

    @property
    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {k: v or "" for k, v in attrs})
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.stack[-1].children.append(Node(tag, {k: v or "" for k, v in attrs}))

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self.stack) - 1, 0, -1):  # close up to the matching open tag
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


def is_slide(node: Node) -> bool:
    return node.tag == "section" or "slide" in node.classes


def is_notes(node: Node) -> bool:
    return node.tag == "aside" and "notes" in node.classes


def find_slides(node: Node) -> list[Node]:
    """Leaf slides under ``node`` in document order (a group of slides is not itself a slide)."""
    found: list[Node] = []
    for child in node.children:
        if not isinstance(child, Node):
            continue
        inner = find_slides(child)
        if is_slide(child) and not inner:
            found.append(child)
        else:
            found.extend(inner)
    return found


def text_of(node: Node | str, skip_notes: bool = True) -> str:
    """Visible text with block elements on their own lines."""
    if isinstance(node, str):
        return re.sub(r"\s+", " ", node)  # source line breaks are just spaces in HTML
    if node.tag in SKIP_TEXT or (skip_notes and is_notes(node)):
        return ""
    inner = "".join(text_of(c, skip_notes) for c in node.children)
    if node.tag in {"td", "th"}:  # table cells read as "a | b | c", like the pptx adapter's tables
        return f"{inner.strip()} | "
    if node.tag in {"p", "li", "div", "tr", "br", "figcaption", *HEADINGS}:
        return f"\n{inner.removesuffix(' | ')}\n"
    return inner


def to_html(node: Node | str) -> str:
    """Serialise a node back to markup, leaving out presenter notes."""
    if isinstance(node, str):
        return escape(node, quote=False)
    if is_notes(node):
        return ""
    attrs = "".join(f' {k}="{escape(v)}"' for k, v in node.attrs.items() if k != "data-notes")
    if node.tag in VOID:
        return f"<{node.tag}{attrs}>"
    raw = node.tag in {"script", "style"}  # their text is not HTML and must not be escaped
    inner = "".join(c if raw and isinstance(c, str) else to_html(c) for c in node.children)
    return f"<{node.tag}{attrs}>{inner}</{node.tag}>"


def tidy(text: str) -> str:
    """Collapse spaces and blank lines."""
    lines = (re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def first(node: Node, tags: tuple[str, ...]) -> Node | None:
    for child in node.children:
        if isinstance(child, Node):
            if child.tag in tags:
                return child
            hit = first(child, tags)
            if hit is not None:
                return hit
    return None


def notes_of(node: Node) -> str:
    aside = first(node, ("aside",))
    parts = [node.attrs.get("data-notes", "")]
    if aside is not None and is_notes(aside):
        parts.append(text_of(aside, skip_notes=False))
    return tidy("\n".join(parts))


def agent_of(n: int, node: Node) -> dict[str, Any] | None:
    """A slide's ``data-agent='{...}'`` layer; it is validated when the slide's agent is resolved."""
    raw = node.attrs.get("data-agent")
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise IngestError(f"slide {n}: data-agent is not valid JSON ({exc.msg})") from exc
    if not isinstance(value, dict):
        raise IngestError(f"slide {n}: data-agent must be a JSON object")
    return value


TARGETS = ("h1", "h2", "h3", "img", "figure", "table")
ELEMENT = re.compile(r'<(\w+)[^>]*\sdata-lectern-id="([^"]+)"')


def tag_elements(node: Node, counts: dict[str, int] | None = None) -> None:
    """Give headings, images, figures and tables a stable ``data-lectern-id`` (``h2-1``, ``img-2`` …)
    when the author did not, so a DNA record can target one of them."""
    counts = {} if counts is None else counts
    for child in node.children:
        if not isinstance(child, Node):
            continue
        if child.tag in TARGETS:
            counts[child.tag] = counts.get(child.tag, 0) + 1
            child.attrs.setdefault("data-lectern-id", f"{child.tag}-{counts[child.tag]}")
        tag_elements(child, counts)


def element_ids(html: str | None) -> list[dict[str, str]]:
    """The targetable elements of a slide's markup: ``[{id, tag}]`` in document order."""
    return [{"id": m.group(2), "tag": m.group(1)} for m in ELEMENT.finditer(html or "")]


def to_slide(n: int, node: Node, styles: str) -> Slide:
    tag_elements(node)
    heading = first(node, HEADINGS)
    title = tidy(text_of(heading)) if heading is not None else ""
    body = tidy(text_of(node))
    if title and body.startswith(title):
        body = body[len(title) :].strip()
    return Slide(
        n=n,
        title=title,
        body=body,
        notes=notes_of(node),
        html=styles + to_html(node),
        persona=node.attrs.get("data-persona") or None,
        agent=agent_of(n, node),
    )


def parse(data: bytes, name: str = "deck.html") -> Deck:
    """Parse an HTML deck into a ``Deck``; ``<style>`` blocks travel with every slide."""
    builder = _TreeBuilder()
    builder.feed(data.decode("utf-8", errors="replace"))
    builder.close()
    root = builder.root
    slides = find_slides(root)
    if not slides:
        raise IngestError(f"{name}: no <section> or .slide elements found")
    title_node = first(root, ("title",))
    title = tidy(text_of(title_node)) if title_node is not None else PurePath(name).stem
    styles = "".join(to_html(n) for n in _all(root, "style"))
    return Deck(title=title, source="html", slides=[to_slide(i + 1, s, styles) for i, s in enumerate(slides)])


def _all(node: Node, tag: str) -> list[Node]:
    out: list[Node] = []
    for child in node.children:
        if isinstance(child, Node):
            out.extend([child] if child.tag == tag else _all(child, tag))
    return out
