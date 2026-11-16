"""Author data → searchable chunks.

Markdown splits at headings, CSV every 20 rows (each chunk repeats the header line), and plain
text every ~200 words. PDF is not supported in v0.1: a pure-Python extractor would not fit the
size budget.
"""

from __future__ import annotations

import csv
import io
from pathlib import PurePath

from lectern.models import IngestError

WORDS_PER_CHUNK = 200
ROWS_PER_CHUNK = 20
KINDS = (".txt", ".md", ".markdown", ".csv")


def chunk_words(text: str, size: int = WORDS_PER_CHUNK) -> list[str]:
    words = text.split()
    return [" ".join(words[i : i + size]) for i in range(0, len(words), size)]


def chunk_markdown(text: str) -> list[str]:
    sections: list[list[str]] = [[]]
    for line in text.splitlines():
        if line.startswith("#") and any(sections[-1]):
            sections.append([])
        sections[-1].append(line)
    out: list[str] = []
    for section in sections:
        out.extend(chunk_words("\n".join(section)))  # an over-long section still splits
    return out


def chunk_csv(text: str, size: int = ROWS_PER_CHUNK) -> list[str]:
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return []
    header, body = rows[0], rows[1:]
    out = []
    for i in range(0, len(body), size):
        lines = [", ".join(header)] + [", ".join(r) for r in body[i : i + size]]
        out.append("\n".join(lines))
    return out


def chunk(name: str, data: bytes) -> list[str]:
    """Split an uploaded file into chunks; raises ``IngestError`` for an unsupported type."""
    suffix = PurePath(name).suffix.lower()
    if suffix not in KINDS:
        raise IngestError(f"{name}: attachments must be one of {', '.join(KINDS)}")
    text = data.decode("utf-8", errors="replace")
    if suffix == ".csv":
        return chunk_csv(text)
    if suffix in (".md", ".markdown"):
        return chunk_markdown(text)
    return chunk_words(text)
