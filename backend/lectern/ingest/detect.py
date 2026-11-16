"""Sniff what kind of deck a file is, from its name and its first bytes."""

from __future__ import annotations

import json

from lectern.models import IngestError, SourceKind

ZIP_MAGIC = b"PK\x03\x04"


def detect(name: str, data: bytes) -> SourceKind:
    """``pptx`` (a zip), ``gslides`` (Slides API JSON) or ``html`` (a Claude artifact deck)."""
    lower = name.lower()
    head = data[:512].lstrip()
    if data.startswith(ZIP_MAGIC):
        if lower.endswith(".pptx") or b"ppt/" in data[:4096]:
            return "pptx"
        raise IngestError(f"{name}: a zip file that is not a .pptx")
    if head.startswith(b"{"):
        try:
            doc = json.loads(data)
        except ValueError as exc:
            raise IngestError(f"{name}: not valid JSON") from exc
        if isinstance(doc, dict) and isinstance(doc.get("slides"), list):
            return "gslides"
        raise IngestError(f"{name}: JSON without a 'slides' list (expected a Slides API export)")
    if head.startswith(b"<") or lower.endswith((".html", ".htm")):
        return "html"
    raise IngestError(f"{name}: unknown deck format (expected .html, .pptx or Slides JSON)")
