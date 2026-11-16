"""Build the sample .pptx decks from the text in this file, byte for byte the same every time.

    uv run python scripts/make_sample_pptx.py           # (re)write both files
    uv run python scripts/make_sample_pptx.py --check   # fail if a checked-in file differs

The repo keeps the .pptx files so a fresh clone works without a build step, but they are only
ever produced by this script: zip timestamps and document dates are fixed so the output is
reproducible. Each slide has a title, text in two boxes placed out of reading order, and
optionally a table, a picture with alt text, and presenter notes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import struct
import sys
import zlib
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
FIXED_TIME = dt.datetime(2026, 1, 1, 9, 0, 0)

SAMPLE = {
    "title": "Sample deck",
    "slides": [
        {"title": "Welcome", "lines": ["A four-slide sample for the tests."], "notes": "Say hello first."},
        {
            "title": "Numbers",
            "lines": ["Visitors grew in March.", "Bottom box, read second."],
            "table": [["Month", "Visitors"], ["February", "120"], ["March", "180"]],
            "notes": "March was the launch month.",
        },
        {"title": "No notes here", "lines": ["This slide deliberately has no presenter notes."]},
        {
            "title": "A picture",
            "lines": ["The chart is an image."],
            "picture": "Bar chart of visitors per month",
            "notes": "Point at the March bar.",
        },
    ],
}

KETTLE = {
    "title": "Kettle & Co. quarterly review",
    "slides": [
        {
            "title": "Kettle & Co. quarterly review",
            "lines": ["Q3 results for the roastery and the three cafes."],
            "notes": "Kettle & Co. is a small coffee roaster. Open with the headline: revenue up 14% on Q2.",
        },
        {
            "title": "Revenue by region",
            "lines": ["All three regions grew; the harbour cafe grew fastest."],
            "table": [
                ["Region", "Q2", "Q3"],
                ["Old town", "41k", "45k"],
                ["Harbour", "28k", "36k"],
                ["Online", "19k", "20k"],
            ],
            "notes": "The harbour cafe grew 29% because the ferry timetable changed in July.",
        },
        {
            "title": "What changed in Q3",
            "lines": [
                "New seasonal blend in August.",
                "Cold brew on tap at the harbour.",
                "Online shipping moved to a weekly batch.",
            ],
            "notes": "The weekly batch cut shipping costs by a fifth but slowed delivery by two days.",
        },
        {
            "title": "What customers said",
            "lines": ["Survey of 212 customers in September."],
            "picture": "Word cloud: friendly, slow online delivery, great cold brew",
        },
        {
            "title": "Plan for Q4",
            "lines": [
                "Hire one barista for the harbour.",
                "Test twice-weekly online shipping.",
                "Holiday gift boxes from November.",
            ],
            "notes": "Ask the board to approve the barista hire today; the rest needs no decision.",
        },
    ],
}

TARGETS = {
    ROOT / "backend/tests/fixtures/decks/sample.pptx": SAMPLE,
    ROOT / "decks/kettle-quarterly-review.pptx": KETTLE,
}


def tiny_png() -> bytes:
    """A 2x2 grey PNG, built by hand so no image library is needed."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    raw = b"".join(b"\x00" + b"\x80\x80\x80" * 2 for _ in range(2))
    header = struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0)
    body = chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    return b"\x89PNG\r\n\x1a\n" + body


def add_slide(prs: Any, spec: dict[str, Any]) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[5])  # "Title Only"
    slide.shapes.title.text = spec["title"]
    lines = spec["lines"]
    # The lower box is added first, so reading order (top, then left) differs from shape order.
    if len(lines) > 1:
        low = slide.shapes.add_textbox(Inches(1), Inches(5.5), Inches(8), Inches(1)).text_frame
        low.text = "\n".join(lines[1:])
    top = slide.shapes.add_textbox(Inches(1), Inches(1.6), Inches(8), Inches(0.8)).text_frame
    top.text = lines[0]
    top.paragraphs[0].runs[0].font.size = Pt(20)
    if "table" in spec:
        rows = spec["table"]
        shape = slide.shapes.add_table(len(rows), len(rows[0]), Inches(1), Inches(2.6), Inches(6), Inches(2))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                shape.table.cell(r, c).text = value
    if "picture" in spec:
        pic = slide.shapes.add_picture(io.BytesIO(tiny_png()), Inches(3), Inches(2.6), Inches(3), Inches(2))
        pic._element.nvPicPr.cNvPr.set("descr", spec["picture"])
    if spec.get("notes"):
        slide.notes_slide.notes_text_frame.text = spec["notes"]


def build(deck: dict[str, Any]) -> bytes:
    prs = Presentation()
    props = prs.core_properties
    props.title, props.author, props.revision = deck["title"], "lectern", 1
    props.created = props.modified = props.last_printed = FIXED_TIME
    for spec in deck["slides"]:
        add_slide(prs, spec)
    buf = io.BytesIO()
    prs.save(buf)
    return normalise_zip(buf.getvalue())


def normalise_zip(data: bytes) -> bytes:
    """Rewrite the zip with fixed timestamps so the bytes never depend on when it was built."""
    import zipfile

    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            fixed = zipfile.ZipInfo(info.filename, date_time=(1980, 1, 1, 0, 0, 0))
            fixed.compress_type = zipfile.ZIP_DEFLATED
            dst.writestr(fixed, src.read(info.filename))
    return out.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="compare instead of writing")
    args = parser.parse_args()
    stale = []
    for path, deck in TARGETS.items():
        data = build(deck)
        if args.check:
            if not path.exists() or path.read_bytes() != data:
                stale.append(path.relative_to(ROOT))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(f"wrote {path.relative_to(ROOT)} ({len(data)} bytes)")
    if stale:
        print(f"out of date (run scripts/make_sample_pptx.py): {', '.join(map(str, stale))}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
