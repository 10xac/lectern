"""Ingest adapters: each turns one source format into the same ``Deck`` model."""

from __future__ import annotations

from collections.abc import Callable

from lectern.ingest import gslides, html_artifact, pptx
from lectern.ingest.detect import detect
from lectern.models import Deck, SourceKind

ADAPTERS: dict[SourceKind, Callable[[bytes, str], Deck]] = {
    "html": html_artifact.parse,
    "pptx": pptx.parse,
    "gslides": gslides.parse,
}

__all__ = ["ADAPTERS", "detect"]
