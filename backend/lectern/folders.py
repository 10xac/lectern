"""Decks as folders: one file per slide (decision D1), and uploads registered as files.

``put_slide("decks/q3/03-revenue.html", …)`` creates the deck ``decks/q3`` on first use and
rebuilds its slides from its live slide files, ordered by ``meta.order`` then path. A slide file
may be an HTML fragment (``<section>`` or bare markup), Markdown or plain text; its metadata can
set ``title``, ``notes``, ``order``, ``persona`` and ``agent`` (its AgentSpec layer).

An uploaded ``.pptx`` or single-file HTML deck is stored whole at ``uploads/<deck id>/<name>``,
and its slides are addressed as ``<file id>#<n>``.
"""

from __future__ import annotations

from typing import Any

from lectern.files import Files, Mode, StoredFile
from lectern.graph.nodes.ingest import label
from lectern.ingest.html_artifact import SLIDE_MARK
from lectern.ingest.html_artifact import parse as parse_html
from lectern.models import Deck, IngestError, Slide
from lectern.store import Store

SLIDE_META = ("title", "notes", "order", "persona", "agent")


def folder_of(path: str) -> str:
    folder, _, name = path.rpartition("/")
    if not folder or not name:
        raise IngestError(f"a slide lives in a deck folder, like decks/q3/01-intro.html (got {path!r})")
    return folder


def parse_slide(file: StoredFile, data: bytes) -> Slide:
    """One slide from one file, with its metadata on top."""
    if file.mime == "text/html":
        try:
            parsed = parse_html(data, file.path)
        except IngestError:
            parsed = parse_html(b"<section>" + data + b"</section>", file.path)
        slide = parsed.slides[0]
        if parsed.shell and slide.html is not None:  # the file's own head (styles, fonts) comes along
            slide = slide.model_copy(update={"html": parsed.shell.replace(SLIDE_MARK, slide.html)})
    else:
        lines = data.decode("utf-8", errors="replace").strip().splitlines()
        head = lines[0].lstrip("# ").strip() if lines else ""
        slide = Slide(n=0, title=head, body="\n".join(lines[1:]).strip())
    meta = file.meta
    return slide.model_copy(
        update={
            "file_id": file.id,
            "title": meta.get("title") or slide.title,
            "notes": meta.get("notes") or slide.notes,
            "persona": meta.get("persona") or slide.persona,
            "agent": meta.get("agent") or slide.agent,
        }
    )


def rebuild(store: Store, files: Files, deck_id: int) -> Deck:
    """Re-read a folder deck's live slide files into its slides (numbers follow the order)."""
    deck = store.get_deck(deck_id)
    assert deck is not None and deck.folder is not None
    prefix = deck.folder + "/"
    live = [
        f
        for f in files.list(prefix, role="slide")
        if f.status == "live" and "/" not in f.path[len(prefix) :]  # direct children only
    ]
    live.sort(key=lambda f: (f.meta.get("order", 1_000_000), f.path))
    slides = []
    for n, file in enumerate(live, start=1):
        _, data = files.read(file.path)
        slides.append(parse_slide(file, data).model_copy(update={"n": n}))
    outline = "\n".join(f"{s.n}. {label(s)}" for s in slides)
    store.replace_slides(deck_id, slides, outline)
    rebuilt = store.get_deck(deck_id)
    assert rebuilt is not None
    return rebuilt


def put_slide(
    store: Store,
    files: Files,
    path: str,
    content: bytes,
    mode: Mode = "upsert",
    meta: dict[str, Any] | None = None,
) -> tuple[Deck, StoredFile]:
    """Create or overwrite one slide file; its folder becomes (or stays) a deck."""
    folder = folder_of(files.clean(path))
    deck_id = store.deck_by_folder(folder)
    created = deck_id is None
    if deck_id is None:
        title = (meta or {}).get("deck_title") or folder.rsplit("/", 1)[-1]
        deck_id = store.add_deck(Deck(title=title, source="folder", folder=folder))
    slide_meta = {k: v for k, v in (meta or {}).items() if k in SLIDE_META}
    try:
        file = files.put(path, content, mode=mode, role="slide", deck_id=deck_id, meta=slide_meta)
    except Exception:
        if created:  # no empty deck is left behind when its first slide could not be stored
            store.delete_deck(deck_id)
        raise
    return rebuild(store, files, deck_id), file


def refresh(store: Store, files: Files, file: StoredFile) -> None:
    """After a slide file moved, changed metadata or vanished, rebuild its deck."""
    if file.role == "slide" and file.deck_id is not None:
        rebuild(store, files, file.deck_id)


def register_upload(store: Store, files: Files, deck_id: int, name: str, data: bytes) -> StoredFile:
    """Keep an uploaded deck's original bytes, so its slides have lasting ids."""
    safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in name) or "deck"
    file = files.put(f"uploads/{deck_id}/{safe}", data, role="deck", deck_id=deck_id)
    store.set_deck_file(deck_id, file.id)
    return file
