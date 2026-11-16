"""Google Slides export (a Slides API ``presentations.get`` JSON) → slides with speaker notes.

Text lives in ``pageElements[].shape.text.textElements[].textRun.content``; tables in
``pageElements[].table.tableRows[].tableCells[].text``. The title is the shape whose placeholder
type is ``TITLE`` or ``CENTERED_TITLE``. Speaker notes are the notes-page shape whose
``objectId`` is the slide's ``speakerNotesObjectId``. No network: the file is an export.
"""

from __future__ import annotations

import json
from pathlib import PurePath
from typing import Any

from lectern.models import Deck, IngestError, Slide

TITLE_TYPES = frozenset({"TITLE", "CENTERED_TITLE"})


def text_content(text: dict[str, Any] | None) -> str:
    """Join a Slides ``text`` object's runs into plain text."""
    if not text:
        return ""
    runs = [el.get("textRun", {}).get("content", "") for el in text.get("textElements", [])]
    return "".join(runs).strip()


def element_lines(element: dict[str, Any]) -> list[str]:
    if "shape" in element:
        content = text_content(element["shape"].get("text"))
        return [line.strip() for line in content.splitlines() if line.strip()]
    if "table" in element:
        rows = element["table"].get("tableRows", [])
        return [" | ".join(text_content(c.get("text")) for c in r.get("tableCells", [])) for r in rows]
    return []


def is_title(element: dict[str, Any]) -> bool:
    placeholder = element.get("shape", {}).get("placeholder", {})
    return placeholder.get("type") in TITLE_TYPES


def speaker_notes(page: dict[str, Any]) -> str:
    """The speaker notes of one slide page."""
    notes_page = page.get("slideProperties", {}).get("notesPage", {})
    notes_id = notes_page.get("notesProperties", {}).get("speakerNotesObjectId")
    for element in notes_page.get("pageElements", []):
        if element.get("objectId") == notes_id:
            return text_content(element.get("shape", {}).get("text"))
    return ""


def to_slide(n: int, page: dict[str, Any]) -> Slide:
    elements = page.get("pageElements", [])
    title = next((text_content(e["shape"].get("text")) for e in elements if is_title(e)), "")
    body = [line for e in elements if not is_title(e) for line in element_lines(e)]
    return Slide(n=n, title=title, body="\n".join(body), notes=speaker_notes(page))


def parse(data: bytes, name: str = "deck.json") -> Deck:
    """Parse a Slides API JSON export into a ``Deck``."""
    try:
        doc = json.loads(data)
    except ValueError as exc:
        raise IngestError(f"{name}: not valid JSON") from exc
    pages = doc.get("slides") if isinstance(doc, dict) else None
    if not isinstance(pages, list):
        raise IngestError(f"{name}: no 'slides' list")
    title = str(doc.get("title") or PurePath(name).stem)
    return Deck(title=title, source="gslides", slides=[to_slide(i + 1, p) for i, p in enumerate(pages)])
