"""PowerPoint slides drawn as HTML: every shape absolutely positioned at its place on a 960 px wide
stage, with its fill, its text (size, weight, colour, alignment) and its pictures.

It is close, not pixel-exact: theme colours and fonts a shape inherits from its master fall back
to sensible defaults, and charts and SmartArt show as their alt text. The original file is kept,
so "Download original" always gives the exact deck. Pictures are returned separately and stored
as files; the markup refers to them through ``MEDIA``, which the caller replaces with their URL.
"""

from __future__ import annotations

import hashlib
import io
from collections.abc import Iterable
from html import escape
from typing import Any

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.enum.text import PP_ALIGN

STAGE = 960
MEDIA = "{{media}}/"
ALIGN = {PP_ALIGN.CENTER: "center", PP_ALIGN.RIGHT: "right", PP_ALIGN.JUSTIFY: "justify"}
TITLES = {PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE}


def rgb(color: Any) -> str | None:
    """A colour as ``#rrggbb`` when the file says it outright (theme colours give None)."""
    try:
        return f"#{color.rgb}" if color is not None and color.type is not None and color.rgb else None
    except (AttributeError, ValueError, TypeError):
        return None


def fill_of(fill: Any) -> str | None:
    try:
        return rgb(fill.fore_color) if fill.type == 1 else None  # MSO_FILL.SOLID
    except (AttributeError, ValueError, TypeError):
        return None


class Drawer:
    def __init__(self, width_emu: int) -> None:
        self.k = STAGE / width_emu  # px per EMU
        self.media: dict[str, bytes] = {}

    def px(self, emu: Any) -> float:
        return round(int(emu or 0) * self.k, 1)

    def pt(self, size: Any, default: float) -> float:
        return round((size.pt if size is not None else default) * 12700 * self.k, 1)

    def box(self, shape: Any, extra: str = "") -> str:
        return (
            f"position:absolute;left:{self.px(shape.left)}px;top:{self.px(shape.top)}px;"
            f"width:{self.px(shape.width)}px;height:{self.px(shape.height)}px;{extra}"
        )

    def shapes(self, shapes: Iterable[Any], skip_placeholders: bool = False) -> str:
        out = []
        for shape in shapes:
            if skip_placeholders and shape.is_placeholder:
                continue
            try:
                out.append(self.shape(shape))
            except Exception:
                continue
        return "".join(out)

    def shape(self, shape: Any) -> str:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            return self.shapes(shape.shapes)
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            return self.picture(shape)
        if getattr(shape, "has_table", False) and shape.has_table:
            return self.table(shape)
        fill = fill_of(shape.fill) if hasattr(shape, "fill") else None
        style = self.box(shape, f"background:{fill};" if fill else "")
        text = self.text(shape) if shape.has_text_frame else ""
        if not text and not fill:
            return ""
        return f'<div style="{style}overflow:hidden">{text}</div>'

    def picture(self, shape: Any) -> str:
        image = shape.image
        name = f"{hashlib.sha256(image.blob).hexdigest()[:24]}.{image.ext}"
        self.media[name] = image.blob
        descr = shape._element.xpath("./*[1]/p:cNvPr/@descr")
        alt = escape(descr[0] if descr else "", quote=True)
        return f'<img src="{MEDIA}{name}" alt="{alt}" style="{self.box(shape, "object-fit:fill")}">'

    def table(self, shape: Any) -> str:
        rows = "".join(
            "<tr>" + "".join(f"<td>{escape(c.text)}</td>" for c in row.cells) + "</tr>"
            for row in shape.table.rows
        )
        css = "border-collapse:collapse;font-size:14px"
        return f'<table style="{self.box(shape, css)}">{rows}</table>'

    def text(self, shape: Any) -> str:
        title = shape.is_placeholder and shape.placeholder_format.type in TITLES
        default = 36.0 if title else 18.0
        paras = []
        for p in shape.text_frame.paragraphs:
            runs = "".join(self.run(r, default, title) for r in p.runs) or "&nbsp;"
            align = ALIGN.get(p.alignment, "left")
            indent = f"padding-left:{p.level * 24}px;" if p.level else ""
            paras.append(f'<p style="margin:0 0 .25em;text-align:{align};{indent}">{runs}</p>')
        return f'<div style="padding:6px 10px">{"".join(paras)}</div>'

    def run(self, run: Any, default: float, title: bool) -> str:
        font = run.font
        css = [f"font-size:{self.pt(font.size, default)}px"]
        if font.bold or (title and font.bold is None):
            css.append("font-weight:700")
        if font.italic:
            css.append("font-style:italic")
        color = rgb(font.color) if font.color and font.color.type is not None else None
        if color:
            css.append(f"color:{color}")
        if font.name:
            css.append(f"font-family:'{escape(font.name)}',Calibri,Arial,sans-serif")
        return f'<span style="{";".join(css)}">{escape(run.text)}</span>'


def render(data: bytes) -> tuple[list[str], dict[str, bytes]]:
    """Each slide's markup, and the pictures it refers to (by file name)."""
    prs = Presentation(io.BytesIO(data))
    width, height = int(prs.slide_width or 9144000), int(prs.slide_height or 5143500)
    draw = Drawer(width)
    stage_h = round(height * draw.k)
    fit = min(1.0, 540 / stage_h)  # a 4:3 deck is scaled to the 16:9 frame's height
    pages = []
    for slide in prs.slides:
        layout = slide.slide_layout
        background = fill_of(slide.background.fill) if slide.background is not None else None
        inner = (
            draw.shapes(layout.slide_master.shapes, skip_placeholders=True)
            + draw.shapes(layout.shapes, skip_placeholders=True)
            + draw.shapes(slide.shapes)
        )
        stage = (
            f"position:relative;width:{STAGE}px;height:{stage_h}px;overflow:hidden;"
            f"background:{background or '#fff'};color:#1f2937;font-family:Calibri,Arial,sans-serif;"
            f"transform:scale({fit});transform-origin:top left"
        )
        pages.append(f'<style>body{{margin:0}}</style><div class="pptx-slide" style="{stage}">{inner}</div>')
    return pages, draw.media
