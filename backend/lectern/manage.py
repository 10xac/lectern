"""Managing decks and slides: rename and delete a deck; update, insert, duplicate, move and delete
a slide. ``Hub`` wraps these so the web app, REST and MCP all do the same thing.

The two kinds of deck change differently:

* a **folder deck** (one file per slide) changes its files: a slide's content is its file, its
  title and notes are the file's metadata, and its position is ``meta.order``;
* an **uploaded deck** (one ``.pptx`` or HTML file) changes its rows. The original file is kept
  as it was uploaded. Before the first change, every slide's lasting id (``<file id>#<n>``) is
  written down, so DNA recorded for a slide stays on that slide when slides move.

Either way each slide's chat thread follows it to its new number (``Store.remap_slides``).
"""

from __future__ import annotations

import uuid
from html import escape
from typing import Any

from lectern.files import FileError, Files
from lectern.folders import rebuild
from lectern.graph.nodes.ingest import label
from lectern.ingest.html_artifact import parse as parse_html
from lectern.models import Deck, IngestError, Slide
from lectern.store import Store

MAX_SLIDES = 200
FIELDS = ("title", "body", "notes", "html")


def plain_html(title: str, body: str) -> str:
    """Markup for a slide written as text: a heading, then one paragraph per line."""
    lines = "".join(f"<p>{escape(line)}</p>" for line in body.splitlines() if line.strip())
    return f"<section><h1>{escape(title)}</h1>{lines}</section>"


def text_of_html(html: str) -> tuple[str, str]:
    """(title, body) read from a slide's markup, so the slide's agent answers from what it shows."""
    try:
        slide = parse_html(html.encode(), "slide.html").slides[0]
    except IngestError:
        slide = parse_html(f"<section>{html}</section>".encode(), "slide.html").slides[0]
    return slide.title, slide.body


def position(at: int | None, count: int) -> int:
    """A 1-based position clamped to the deck (``None``: the end)."""
    return count + 1 if at is None else max(1, min(at, count + 1))


class Manager:
    def __init__(self, store: Store, files: Files) -> None:
        self.store, self.files = store, files

    # decks --------------------------------------------------------------------------------------

    def delete_deck(self, deck: Deck) -> None:
        """The deck, its slides, threads, jobs, DNA, attachments, traces, files and their blobs."""
        assert deck.id is not None
        for file in self.files.list(deck_id=deck.id):
            try:
                self.files.blobs.delete(file.path)
            except OSError as exc:
                raise FileError(503, f"could not delete {file.path}: {exc.strerror}") from exc
        self.store.delete_deck(deck.id)

    # slides -------------------------------------------------------------------------------------

    def update(self, deck: Deck, n: int, patch: dict[str, Any]) -> None:
        slide = deck.slide(n)
        assert slide is not None and deck.id is not None
        patch = {k: v for k, v in patch.items() if k in FIELDS and v is not None}
        if patch.get("html") == "":  # an emptied HTML field: show the slide as text again
            patch.pop("html")
            if deck.folder is None:
                patch["html"] = None
        if deck.folder is not None:
            self._update_file(deck, slide, patch)
            return
        if patch.get("html") is None:
            self._save(deck, [slide.model_copy(update=patch) if s.n == n else s for s in deck.slides])
            return
        if "html" in patch and "body" not in patch:
            title, body = text_of_html(patch["html"])
            patch = {"body": body, "title": patch.get("title") or title or slide.title} | patch
        self._save(deck, [slide.model_copy(update=patch) if s.n == n else s for s in deck.slides])

    def _update_file(self, deck: Deck, slide: Slide, patch: dict[str, Any]) -> None:
        assert slide.file_id is not None and deck.id is not None
        file = self.files.by_id(slide.file_id)
        meta: dict[str, Any] = {k: patch[k] for k in ("title", "notes") if k in patch}
        if "html" in patch or "body" in patch:
            content = patch.get("html") or self._text_content(
                file.path, patch.get("title") or slide.title, patch["body"]
            )
            self.files.put(file.path, content.encode(), mode="overwrite", role="slide", meta=meta)
        elif meta:
            self.files.update_meta(file.path, meta)
        rebuild(self.store, self.files, deck.id)

    @staticmethod
    def _text_content(path: str, title: str, body: str) -> str:
        return plain_html(title, body) if path.endswith((".html", ".htm")) else f"# {title}\n\n{body}\n"

    def insert(self, deck: Deck, at: int | None, fields: dict[str, Any], like: Slide | None = None) -> int:
        """A new slide at ``at`` (or a copy of ``like`` after it); returns its number."""
        assert deck.id is not None
        if len(deck.slides) >= MAX_SLIDES:
            raise FileError(422, f"a deck holds at most {MAX_SLIDES} slides")
        at = position(at, len(deck.slides))
        if like is not None:
            fields = {k: getattr(like, k) for k in FIELDS} | {"persona": like.persona, "agent": like.agent}
        title, body = fields.get("title") or "", fields.get("body") or ""
        if fields.get("html") and not body:
            title, body = (title or text_of_html(fields["html"])[0]), text_of_html(fields["html"])[1]
        if deck.folder is not None:
            self._insert_file(deck, at, title, body, fields, like)
            return at
        base = deck.file_id or f"deck-{deck.id}"
        new = Slide(
            n=0,
            title=title,
            body=body,
            notes=fields.get("notes") or "",
            html=fields.get("html"),
            persona=fields.get("persona"),
            agent=fields.get("agent"),
            ref=f"{base}#s{uuid.uuid4().hex[:8]}",
        )
        slides = list(deck.slides)
        slides.insert(at - 1, new)
        self._save(deck, slides)
        return at

    def _insert_file(
        self, deck: Deck, at: int, title: str, body: str, fields: dict[str, Any], like: Slide | None
    ) -> None:
        assert deck.folder is not None and deck.id is not None
        meta = {k: v for k, v in (("title", title), ("notes", fields.get("notes"))) if v}
        if like is not None and like.file_id is not None:
            source, data = self.files.read(self.files.by_id(like.file_id).path)
            stem, dot, ext = source.path.rpartition("/")[2].rpartition(".")
            name = f"{stem or ext}-copy-{uuid.uuid4().hex[:4]}{dot}{ext if stem else ''}"
            meta = {k: v for k, v in source.meta.items() if k != "order"}
        else:
            ext = "html" if fields.get("html") else "md"
            name = f"slide-{uuid.uuid4().hex[:6]}.{ext}"
            data = (fields.get("html") or self._text_content(name, title, body)).encode()
        file = self.files.put(
            f"{deck.folder}/{name}", data, mode="create", role="slide", deck_id=deck.id, meta=meta
        )
        order = [s.file_id for s in deck.slides]
        order.insert(at - 1, file.id)
        self._order_files(deck, order)

    def move(self, deck: Deck, n: int, to: int) -> None:
        slides = [s for s in deck.slides if s.n != n]
        slide = deck.slide(n)
        assert slide is not None
        slides.insert(position(to, len(slides)) - 1, slide)
        if deck.folder is not None:
            self._order_files(deck, [s.file_id for s in slides])
        else:
            self._save(deck, slides)

    def delete(self, deck: Deck, n: int) -> None:
        slide = deck.slide(n)
        assert slide is not None and deck.id is not None
        if slide.file_id is not None:
            self.files.delete(self.files.by_id(slide.file_id).path, purge=True)
            rebuild(self.store, self.files, deck.id)
        else:
            self._save(deck, [s for s in deck.slides if s.n != n])

    # helpers ------------------------------------------------------------------------------------

    def _order_files(self, deck: Deck, file_ids: list[str | None]) -> None:
        assert deck.id is not None
        for i, file_id in enumerate(file_ids, start=1):
            if file_id is not None:
                self.files.update_meta(self.files.by_id(file_id).path, {"order": i * 10})
        rebuild(self.store, self.files, deck.id)

    def _save(self, deck: Deck, slides: list[Slide]) -> None:
        """An uploaded deck's slides, renumbered, each keeping its lasting id."""
        assert deck.id is not None
        kept = [
            s.model_copy(update={"n": i, "ref": deck.slide_ref(s)}) for i, s in enumerate(slides, start=1)
        ]
        self.store.replace_slides(deck.id, kept, "\n".join(f"{s.n}. {label(s)}" for s in kept))
