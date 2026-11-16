"""The MCP server: an AI tool building a deck can do what an author does in the web app.

Run it with ``lectern mcp`` (stdio) or reach it at ``/mcp`` on the API (streamable HTTP; with login
on, it needs a personal access token: ``Authorization: Bearer lectern_pat_…``). Every tool calls ``Hub``,
the same facade the REST API uses, and its input schema comes from the Hub's pydantic models.
Influences added here are recorded ``via: mcp`` with the client's name as their author.
"""

from __future__ import annotations

import base64
import functools
import inspect
from collections.abc import Callable
from typing import Any, Literal

import httpx
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import ValidationError

from lectern.agents.spec import SpecError
from lectern.dna import Author, Influence, InfluenceIn, InfluencePatch, Ref
from lectern.files import MAX_BYTES, FileError, Mode, Reconciled, StoredFile
from lectern.hub import Hub
from lectern.models import IngestError, Job

INSTRUCTIONS = (
    "lectern keeps a deck's slides and their conceptual DNA: what shaped each slide (ideas, reasoning, "
    "notes, citations, references) with a degree of influence. While you build a deck, put each slide "
    "with put_slide and log why it looks the way it does with add_influence(s). Address slides by deck "
    "id and number, files by relative path."
)


def by_ai(ctx: Context | None, data: InfluenceIn, model: str | None) -> InfluenceIn:
    """Fill in who wrote it: the MCP client's name, and the model it says it is."""
    info = getattr(getattr(getattr(ctx, "session", None), "client_params", None), "client_info", None)
    client = getattr(info, "name", None) or data.author.name
    request = getattr(getattr(ctx, "request_context", None), "request", None)
    person = getattr(getattr(request, "state", None), "user", None)  # the owner of the access token
    name = f"{client} for {person.email}" if person is not None else client
    author = Author(type="ai", name=name[:100], tool=client, model=model or data.author.model)
    return data.model_copy(update={"author": author})


def fetch(url: str) -> bytes:
    if not url.startswith(("https://", "http://")):
        raise ValueError("only http(s) URLs")
    resp = httpx.get(url, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    if len(resp.content) > MAX_BYTES:
        raise ValueError("files are limited to 20 MB")
    return resp.content


class Tools:
    """The MCP tools. Each public method is one tool; its docstring is the tool's description."""

    def __init__(self, hub: Hub) -> None:
        self.hub = hub

    def list_decks(self) -> list[dict[str, Any]]:
        """Every deck: id, title and source."""
        return self.hub.list_decks()

    def get_deck(self, deck_id: int) -> dict[str, Any]:
        """A deck with its slides; each slide has its lasting ref, file path and element ids to target."""
        return self.hub.get_deck(deck_id)

    def get_slide(self, deck_id: int, n: int) -> dict[str, Any]:
        """One slide (title, body, notes, html, element ids) and its DNA trace."""
        deck = self.hub.deck(deck_id, n)
        return self.hub.slide_info(deck, n) | self.hub.get_dna(deck_id, n, "text")

    def create_deck(
        self, name: str, content_base64: str | None = None, url: str | None = None
    ) -> dict[str, Any]:
        """Upload a whole deck (HTML, .pptx or Google Slides JSON) as base64 or from a URL."""
        data = base64.b64decode(content_base64) if content_base64 else fetch(url or "")
        return self.hub.get_deck(self.hub.create_deck(name, data).id or 0)

    def put_slide(
        self, path: str, content: str, mode: Mode = "upsert", meta: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Create or overwrite one slide file (HTML fragment or Markdown), e.g. decks/q3/03-revenue.html.
        Its folder is the deck. Overwriting keeps the slide's id and its DNA. meta: title, notes, order,
        persona, agent, deck_title."""
        return self.hub.put_slide(path, content.encode(), mode, meta)

    def read_slide(self, path: str) -> dict[str, Any]:
        """A slide file's content, metadata, deck, number and DNA trace."""
        return self.hub.read_slide(path)

    def update_slide_meta(self, path: str, meta: dict[str, Any]) -> StoredFile:
        """Merge metadata into a file (title, notes, order, persona, agent …); a null value removes a key."""
        return self.hub.update_meta(path, meta)

    def put_file(
        self, path: str, content_base64: str, mode: Mode = "upsert", deck_id: int | None = None
    ) -> StoredFile:
        """Store any file (image, PDF, text) at a relative path; overwriting keeps its id and metadata."""
        return self.hub.put_file(path, base64.b64decode(content_base64), mode, deck_id)

    def read_file(self, path: str) -> dict[str, Any]:
        """A file's metadata and contents (text as is, anything else as base64)."""
        file, data = self.hub.files.read(path)
        text = file.mime.startswith("text/") or file.mime == "application/json"
        body = (
            {"text": data.decode("utf-8", "replace")} if text else {"base64": base64.b64encode(data).decode()}
        )
        return {"file": file.model_dump()} | body

    def list_files(self, prefix: str = "", deck_id: int | None = None) -> list[StoredFile]:
        """Registered files under a path prefix, with id, version and status (live or missing)."""
        return self.hub.files.list(prefix, deck_id)

    def move_file(self, src: str, dst: str) -> StoredFile:
        """Rename a file; its id, version and metadata stay, so its DNA follows it."""
        return self.hub.move(src, dst)

    def delete_file(self, path: str, purge: bool = False) -> StoredFile:
        """Delete a file's contents; its metadata stays (missing) for an author to relink, unless purge."""
        return self.hub.delete(path, purge)

    def reconcile_files(self) -> Reconciled:
        """Find files whose contents vanished and contents no file knows, with same-hash suggestions."""
        return self.hub.reconcile()

    def relink_file(self, file_id: str, path: str) -> StoredFile:
        """Attach a missing file's id and metadata to the contents now at path."""
        return self.hub.relink(file_id, path)

    def upload_file(self, deck_id: int, name: str, content_base64: str) -> StoredFile:
        """Upload a reference (image, PDF ≤ 20 MB, text) for a deck; cite it with add_reference."""
        return self.hub.upload_reference(deck_id, name, base64.b64decode(content_base64))

    def add_influence(
        self, deck_id: int, influence: InfluenceIn, model: str | None = None, ctx: Context | None = None
    ) -> Influence:
        """Record what shaped one slide (scope slide), some slides (slides: [2,3,5]) or the whole deck."""
        return self.hub.add_influence(deck_id, by_ai(ctx, influence, model), "mcp")

    def add_influences(
        self,
        deck_id: int,
        influences: list[InfluenceIn],
        model: str | None = None,
        ctx: Context | None = None,
    ) -> list[Influence]:
        """A batch, all or nothing: log the DNA of every slide of a deck in one call."""
        return self.hub.add_influences(deck_id, [by_ai(ctx, i, model) for i in influences], "mcp")

    def update_influence(self, deck_id: int, influence_id: str, patch: InfluencePatch) -> Influence:
        """Change an influence; its previous version is kept in its history."""
        return self.hub.update_influence(deck_id, influence_id, patch)

    def remove_influence(self, deck_id: int, influence_id: str) -> str:
        """Remove an influence (its last version stays in the history)."""
        self.hub.dna.remove(deck_id, influence_id)
        return "removed"

    def list_influences(
        self, deck_id: int, slide: int | None = None, kind: str | None = None, degree: str | None = None
    ) -> list[Influence]:
        """The deck's influences; with slide, those that shape it (deck-wide ones included)."""
        self.hub.deck(deck_id)
        return self.hub.dna.list(deck_id, slide, kind, degree)

    def add_reference(self, deck_id: int, influence_id: str, ref: Ref) -> Influence:
        """Add a URL or an uploaded file (by file_id or path) to an influence's references."""
        refs = [*self.hub.dna.get(deck_id, influence_id).refs, ref]
        return self.hub.update_influence(deck_id, influence_id, InfluencePatch(refs=refs))

    def get_dna(
        self, deck_id: int, slide: int | None = None, format: Literal["graph", "text"] = "text"
    ) -> dict[str, Any]:
        """The DNA of a slide or the whole deck: an ordered text trace, or the graph (nodes, edges)."""
        return self.hub.get_dna(deck_id, slide, format)

    async def ask(self, deck_id: int, question: str, slide: int | None = None) -> dict[str, str]:
        """Ask a slide (or, without slide, the deck). It runs in the background: poll get_job."""
        return {"job_id": self.hub.ask(deck_id, slide, question).id}

    def get_job(self, job_id: str) -> Job:
        """A job's status, answer (with citations) and per-source confidence."""
        return self.hub.get_job(job_id)


TOOLS = [name for name in vars(Tools) if not name.startswith("_")]


def readable(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Turn lectern's own errors into tool errors whose message the AI can read and act on."""

    errors = (FileError, IngestError, SpecError, ValidationError, ValueError)

    @functools.wraps(fn)
    def call(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except errors as exc:
            raise ToolError(str(exc)) from exc

    @functools.wraps(fn)
    async def acall(*args: Any, **kwargs: Any) -> Any:
        try:
            return await fn(*args, **kwargs)
        except errors as exc:
            raise ToolError(str(exc)) from exc

    return acall if inspect.iscoroutinefunction(fn) else call


def build(hub: Hub) -> MCPServer:
    """An MCP server whose tools call ``hub``."""
    mcp = MCPServer("lectern", instructions=INSTRUCTIONS)
    tools = Tools(hub)
    for name in TOOLS:
        mcp.add_tool(readable(getattr(tools, name)), name=name)
    return mcp
