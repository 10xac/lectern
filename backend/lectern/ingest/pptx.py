"""PowerPoint (``.pptx``) → slides with presenter notes, via ``python-pptx``.

Per slide: the title placeholder, then every other shape in reading order (top, then left):
text frames line by line, tables as ``a | b | c`` rows, and picture alt text as
``[image: ...]``. Notes come from the slide's own notes page, when it has one. A Google Slides
"Download as .pptx" file goes through here too.
"""

from __future__ import annotations

import io
from pathlib import Path, PurePath
from typing import Any

from pptx import Presentation
from pptx.util import Emu

from lectern.models import Deck, IngestError, Slide


def _reading_order(shape: Any) -> tuple[int, int]:
    return (int(shape.top or Emu(0)), int(shape.left or Emu(0)))


def shape_lines(shape: Any) -> list[str]:
    """The text a shape shows, one string per line."""
    if shape.has_text_frame:
        return [p.text.strip() for p in shape.text_frame.paragraphs if p.text.strip()]
    if getattr(shape, "has_table", False) and shape.has_table:
        return [" | ".join(cell.text.strip() for cell in row.cells) for row in shape.table.rows]
    alt = shape._element.xpath("./*[1]/p:cNvPr/@descr")  # picture (and other shape) alt text
    return [f"[image: {alt[0].strip()}]"] if alt and alt[0].strip() else []


def notes_text(slide: Any) -> str:
    """The presenter notes of this slide, or an empty string."""
    if not slide.has_notes_slide:
        return ""
    return str(slide.notes_slide.notes_text_frame.text).strip()


def to_slide(n: int, slide: Any) -> Slide:
    title_shape = slide.shapes.title
    title = title_shape.text_frame.text.strip() if title_shape is not None else ""
    others = [s for s in slide.shapes if title_shape is None or s.shape_id != title_shape.shape_id]
    lines = [line for shape in sorted(others, key=_reading_order) for line in shape_lines(shape)]
    return Slide(n=n, title=title, body="\n".join(lines), notes=notes_text(slide))


def parse(data: bytes, name: str = "deck.pptx") -> Deck:
    """Parse ``.pptx`` bytes into a ``Deck``."""
    try:
        prs = Presentation(io.BytesIO(data))
    except Exception as exc:  # python-pptx raises several types for a broken file
        raise IngestError(f"{name}: not a readable .pptx ({type(exc).__name__})") from exc
    title = (prs.core_properties.title or "").strip() or PurePath(name).stem
    slides = [to_slide(i + 1, s) for i, s in enumerate(prs.slides)]
    return Deck(title=title, source="pptx", slides=slides)


def load_deck(path: str | Path) -> Deck:
    """Parse a ``.pptx`` file from disk (handy in a REPL and in tests)."""
    p = Path(path)
    return parse(p.read_bytes(), p.name)
