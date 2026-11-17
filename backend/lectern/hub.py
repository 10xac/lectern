"""One facade over the file registry, folder decks, DNA and jobs. The parity rule: REST
(``dna/routes.py``), MCP (``mcp_server.py``) and the CLI call these methods and nothing else, so
anything one surface can do, the others can do too.
"""

from __future__ import annotations

from typing import Any, Literal

from lectern import folders, service
from lectern.dna import DNA, Influence, InfluenceIn, InfluencePatch, Via
from lectern.dna import graph as dna_graph
from lectern.files import FileError, Files, Mode, Reconciled, StoredFile
from lectern.ingest.html_artifact import element_ids
from lectern.jobs.manager import JobManager
from lectern.models import Deck, Job
from lectern.oauth import OAuth
from lectern.settings import Settings
from lectern.store import Store
from lectern.users import Users


class Hub:
    def __init__(
        self,
        store: Store,
        files: Files,
        dna: DNA,
        jobs: JobManager,
        users: Users,
        settings: Settings,
        oauth: OAuth,
    ) -> None:
        self.store, self.files, self.dna, self.jobs = store, files, dna, jobs
        self.users, self.settings, self.oauth = users, settings, oauth

    # decks and slides ---------------------------------------------------------------------------

    def deck(self, deck_id: int, n: int | None = None) -> Deck:
        deck = self.store.get_deck(deck_id)
        if deck is None:
            raise FileError(404, f"no deck {deck_id}")
        if n is not None and deck.slide(n) is None:
            raise FileError(404, f"deck {deck_id} has no slide {n}")
        return deck

    def list_decks(self) -> list[dict[str, Any]]:
        return [{"id": d.id, "title": d.title, "source": d.source} for d in self.store.list_decks()]

    def slide_info(self, deck: Deck, n: int) -> dict[str, Any]:
        """A slide with what an AI needs to target it: its lasting id, file path and element ids."""
        slide = deck.slide(n)
        assert slide is not None
        path = self.files.by_id(slide.file_id).path if slide.file_id else None
        return slide.model_dump() | {
            "ref": deck.slide_ref(slide),
            "path": path,
            "elements": element_ids(slide.html),
        }

    def get_deck(self, deck_id: int) -> dict[str, Any]:
        deck = self.deck(deck_id)
        return deck.model_dump(exclude={"slides"}) | {
            "slides": [self.slide_info(deck, s.n) for s in deck.slides]
        }

    def create_deck(self, name: str, data: bytes) -> Deck:
        """Upload a whole deck (HTML, pptx or Google Slides JSON); its original is kept as a file."""
        run = service.run_ingest(self.store, name, data)
        if run.state.deck_id is None:
            raise FileError(422, run.outcome or "refused")
        folders.register_upload(self.store, self.files, run.state.deck_id, name, data)
        return self.deck(run.state.deck_id)

    def put_slide(
        self, path: str, content: bytes, mode: Mode = "upsert", meta: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        deck, file = folders.put_slide(self.store, self.files, path, content, mode, meta)
        slide = next(s for s in deck.slides if s.file_id == file.id)
        return {"deck_id": deck.id, "slide": self.slide_info(deck, slide.n), "file": file.model_dump()}

    def edit_slide(self, deck_id: int, n: int, title: str | None, notes: str | None) -> dict[str, Any]:
        """A slide's title or presenter notes. A folder deck's slide keeps them in its file's metadata."""
        deck = self.deck(deck_id, n)
        slide = deck.slide(n)
        assert slide is not None
        if slide.file_id is not None:
            patch = {k: v for k, v in (("title", title), ("notes", notes)) if v is not None}
            self.update_meta(self.files.by_id(slide.file_id).path, patch)
        else:
            self.store.edit_slide(deck_id, n, title, notes)
        return self.slide_info(self.deck(deck_id), n)

    def read_slide(self, path: str) -> dict[str, Any]:
        """A slide file's content, metadata and DNA trace (a folder deck's slide)."""
        file, data = self.files.read(path)
        out: dict[str, Any] = {"file": file.model_dump(), "content": data.decode("utf-8", errors="replace")}
        if file.deck_id is not None:
            deck = self.deck(file.deck_id)
            slide = next((s for s in deck.slides if s.file_id == file.id), None)
            if slide is not None:
                out |= {"deck_id": deck.id, "n": slide.n, "dna": dna_graph.text(self.dna, deck, slide.n)}
        return out

    # files --------------------------------------------------------------------------------------

    def put_file(
        self, path: str, data: bytes, mode: Mode = "upsert", deck_id: int | None = None
    ) -> StoredFile:
        """A reference file (image, PDF, text) or any other blob; slides go through ``put_slide``."""
        return self.files.put(path, data, mode=mode, deck_id=deck_id)

    def upload_reference(self, deck_id: int, name: str, data: bytes) -> StoredFile:
        self.deck(deck_id)
        return self.files.put(f"refs/{deck_id}/{name}", data, deck_id=deck_id)

    def update_meta(self, path: str, patch: dict[str, Any]) -> StoredFile:
        file = self.files.update_meta(path, patch)
        folders.refresh(self.store, self.files, file)
        return file

    def move(self, src: str, dst: str) -> StoredFile:
        file = self.files.move(src, dst)
        folders.refresh(self.store, self.files, file)
        return file

    def delete(self, path: str, purge: bool = False) -> StoredFile:
        file = self.files.delete(path, purge)
        folders.refresh(self.store, self.files, file)
        return file

    def reconcile(self) -> Reconciled:
        found = self.files.reconcile()
        for deck_id in {f.deck_id for f in found.missing if f.role == "slide" and f.deck_id is not None}:
            folders.rebuild(self.store, self.files, deck_id)
        return found

    def relink(self, file_id: str, path: str) -> StoredFile:
        file = self.files.relink(file_id, path)
        folders.refresh(self.store, self.files, file)
        return file

    def forget(self, file_id: str) -> None:
        """Delete a missing file's metadata for good (the UI's "Delete metadata")."""
        self.files.purge(file_id)

    # DNA ----------------------------------------------------------------------------------------

    def add_influence(self, deck_id: int, data: InfluenceIn, via: Via) -> Influence:
        return self.dna.add(deck_id, data, via)

    def add_influences(self, deck_id: int, items: list[InfluenceIn], via: Via) -> list[Influence]:
        """A batch, all or nothing: every item is checked before any is stored."""
        deck = self.deck(deck_id)
        for item in items:
            self.dna._resolve(deck, item)
        return [self.dna.add(deck_id, item, via) for item in items]

    def get_dna(
        self, deck_id: int, n: int | None = None, fmt: Literal["graph", "text"] = "graph"
    ) -> dict[str, Any]:
        deck = self.deck(deck_id, n)
        if fmt == "text":
            return {"text": dna_graph.text(self.dna, deck, n)}
        return dna_graph.graph(self.dna, deck, n)

    def update_influence(self, deck_id: int, influence_id: str, patch: InfluencePatch) -> Influence:
        return self.dna.update(deck_id, influence_id, patch)

    # jobs ---------------------------------------------------------------------------------------

    def ask(self, deck_id: int, n: int | None, question: str, viewer: str = "") -> Job:
        """Start a job (needs a running event loop); poll ``get_job`` or stream its events."""
        return self.jobs.submit(self.deck(deck_id, n), n, question, viewer=viewer)

    def get_job(self, job_id: str) -> Job:
        job = self.jobs.rows.get(job_id)
        if job is None:
            raise FileError(404, f"no job {job_id}")
        return job
