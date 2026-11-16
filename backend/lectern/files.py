"""The file registry: a permanent id per file, its relative path as a renamable alias (decision D1).

Bytes live in the blob store under the path; the ``files`` row keeps the id, path, hash, size,
type, version, status and free metadata (title, notes, order …). Everything that refers to a file
(slides, influences, references) stores its **id**, so:

* **overwrite** keeps the id and adds 1 to ``version``;
* **move** changes only the path;
* **delete** removes the bytes and marks the row ``missing`` (its metadata stays) unless purged;
* **reconcile** finds rows whose bytes vanished and bytes no row knows, and suggests a match when
  the hashes are equal (a rename done outside lectern); **relink** re-attaches a row to a path.
"""

from __future__ import annotations

import hashlib
import io
import json
import mimetypes
import re
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

from lectern.blobs import BadPath, BlobStore, clean_path
from lectern.store import Store

MAX_BYTES = 20 * 1024 * 1024
TEXT_CHARS = 200_000
Role = Literal["slide", "deck", "reference"]
Mode = Literal["create", "overwrite", "upsert"]
SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
  id TEXT PRIMARY KEY, path TEXT NOT NULL UNIQUE, deck_id INTEGER, role TEXT NOT NULL,
  mime TEXT NOT NULL, size INTEGER NOT NULL, sha256 TEXT NOT NULL, version INTEGER NOT NULL,
  status TEXT NOT NULL, meta TEXT NOT NULL, text TEXT NOT NULL);
"""
EXTRA_TYPES = {".md": "text/markdown", ".csv": "text/csv", ".pptx": "application/vnd.openxmlformats-"
               "officedocument.presentationml.presentation", ".json": "application/json"}  # fmt: skip


class FileError(Exception):
    """A registry request that cannot be done; ``status`` is the HTTP status it maps to."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


class StoredFile(BaseModel):
    id: str
    path: str
    deck_id: int | None = None
    role: Role = "reference"
    mime: str
    size: int
    sha256: str
    version: int = 1
    status: Literal["live", "missing"] = "live"
    meta: dict[str, Any] = Field(default_factory=dict)


class Reconciled(BaseModel):
    missing: list[StoredFile]  # rows whose bytes are gone (now marked missing)
    unregistered: list[str]  # paths in the blob store that no row knows
    suggestions: dict[str, str]  # file id → an unregistered path with the same sha256


def mime_of(path: str) -> str:
    ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return EXTRA_TYPES.get(ext) or mimetypes.guess_type(path)[0] or "application/octet-stream"


def extract_text(mime: str, data: bytes) -> str:
    """Searchable text: PDF pages joined by form feeds, text as is, HTML without tags, else nothing."""
    if mime == "application/pdf":
        from pypdf import PdfReader

        try:
            pages = [page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages]
        except Exception as exc:  # a broken PDF is still stored, it just isn't searchable
            raise FileError(422, f"cannot read this PDF: {type(exc).__name__}") from exc
        return "\f".join(pages)[:TEXT_CHARS]
    if mime.startswith("text/") or mime == "application/json":
        text = data.decode("utf-8", errors="replace")
        return re.sub(r"<[^>]+>", " ", text)[:TEXT_CHARS] if mime == "text/html" else text[:TEXT_CHARS]
    return ""


class Files:
    """The registry. All writes go through here, whichever surface asked (UI, REST, MCP, CLI)."""

    def __init__(self, store: Store, blobs: BlobStore) -> None:
        self.store, self.blobs = store, blobs
        with store.tx() as db:
            db.executescript(SCHEMA)

    # reads ------------------------------------------------------------------------------------

    def _row(self, sql: str, arg: object) -> StoredFile | None:
        with self.store.tx() as db:
            row = db.execute(f"SELECT * FROM files WHERE {sql}", (arg,)).fetchone()
        return None if row is None else self._file(row)

    @staticmethod
    def _file(row: Any) -> StoredFile:
        data = {k: row[k] for k in row.keys() if k not in ("meta", "text")}  # noqa: SIM118
        return StoredFile(**data, meta=json.loads(row["meta"]))

    def get(self, path: str) -> StoredFile:
        found = self._row("path = ?", self.clean(path))
        if found is None:
            raise FileError(404, f"no file at {path}")
        return found

    def by_id(self, file_id: str) -> StoredFile:
        found = self._row("id = ?", file_id)
        if found is None:
            raise FileError(404, f"no file {file_id}")
        return found

    def read(self, path: str) -> tuple[StoredFile, bytes]:
        file = self.get(path)
        try:
            return file, self.blobs.get(file.path)
        except FileNotFoundError as exc:
            raise FileError(
                410, f"{path} is registered but its contents are missing; relink or delete it"
            ) from exc

    def text(self, file_id: str) -> str:
        with self.store.tx() as db:
            row = db.execute("SELECT text FROM files WHERE id = ?", (file_id,)).fetchone()
        return "" if row is None else str(row["text"])

    def list(
        self, prefix: str = "", deck_id: int | None = None, role: Role | None = None
    ) -> list[StoredFile]:
        with self.store.tx() as db:
            rows = db.execute(
                "SELECT * FROM files WHERE path LIKE ? ORDER BY path", (prefix + "%",)
            ).fetchall()
        files = [self._file(r) for r in rows]
        return [
            f for f in files if (deck_id is None or f.deck_id == deck_id) and (role is None or f.role == role)
        ]

    # writes -----------------------------------------------------------------------------------

    @staticmethod
    def clean(path: str) -> str:
        try:
            return clean_path(path)
        except BadPath as exc:
            raise FileError(422, str(exc)) from exc

    def put(
        self,
        path: str,
        data: bytes,
        mode: Mode = "upsert",
        role: Role = "reference",
        deck_id: int | None = None,
        meta: dict[str, Any] | None = None,
        mime: str | None = None,
    ) -> StoredFile:
        """Create or overwrite the file at ``path``. Overwriting keeps its id and metadata."""
        path = self.clean(path)
        if len(data) > MAX_BYTES:
            raise FileError(413, f"files are limited to {MAX_BYTES // (1024 * 1024)} MB")
        old = self._row("path = ?", path)
        if old is not None and mode == "create":
            raise FileError(409, f"{path} already exists; overwrite it or pick another path")
        if old is None and mode == "overwrite":
            raise FileError(404, f"no file at {path} to overwrite")
        kind = mime or mime_of(path)
        text = extract_text(kind, data)
        self.blobs.put(path, data)
        sha, size = hashlib.sha256(data).hexdigest(), len(data)
        with self.store.tx() as db:
            if old is None:
                file_id = uuid.uuid4().hex[:12]
                db.execute(
                    "INSERT INTO files (id, path, deck_id, role, mime, size, sha256, version, status, meta,"
                    " text) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 'live', ?, ?)",
                    (file_id, path, deck_id, role, kind, size, sha, json.dumps(meta or {}), text),
                )
            else:
                file_id = old.id
                merged = old.meta | (meta or {})
                db.execute(
                    # The version counts content changes: the same bytes again (a relink) keep it.
                    "UPDATE files SET version = version + (sha256 != ?), mime = ?, size = ?, sha256 = ?,"
                    " status = 'live', meta = ?, text = ?, deck_id = COALESCE(deck_id, ?) WHERE id = ?",
                    (sha, kind, size, sha, json.dumps(merged), text, deck_id, file_id),
                )
        return self.by_id(file_id)

    def update_meta(self, path: str, patch: dict[str, Any]) -> StoredFile:
        """Merge ``patch`` into the file's metadata; a ``None`` value removes that key."""
        file = self.get(path)
        meta = {k: v for k, v in (file.meta | patch).items() if v is not None}
        with self.store.tx() as db:
            db.execute("UPDATE files SET meta = ? WHERE id = ?", (json.dumps(meta), file.id))
        return self.by_id(file.id)

    def set_deck(self, file_id: str, deck_id: int) -> None:
        with self.store.tx() as db:
            db.execute("UPDATE files SET deck_id = ? WHERE id = ?", (deck_id, file_id))

    def move(self, src: str, dst: str) -> StoredFile:
        """Rename: the bytes move to ``dst``; the id, version and metadata stay."""
        file, data = self.read(src)
        dst = self.clean(dst)
        if self._row("path = ?", dst) is not None:
            raise FileError(409, f"{dst} already exists")
        self.blobs.put(dst, data)
        with self.store.tx() as db:
            db.execute("UPDATE files SET path = ? WHERE id = ?", (dst, file.id))
        self.blobs.delete(file.path)
        return self.by_id(file.id)

    def delete(self, path: str, purge: bool = False) -> StoredFile:
        """Remove the bytes. The row stays ``missing`` (to relink later) unless ``purge``."""
        file = self.get(path)
        self.blobs.delete(file.path)
        with self.store.tx() as db:
            if purge:
                db.execute("DELETE FROM files WHERE id = ?", (file.id,))
            else:
                db.execute("UPDATE files SET status = 'missing' WHERE id = ?", (file.id,))
        return file.model_copy(update={"status": "missing"})

    def purge(self, file_id: str) -> None:
        """Forget a missing file's row (the UI's "Delete metadata")."""
        file = self.by_id(file_id)
        self.blobs.delete(file.path)
        with self.store.tx() as db:
            db.execute("DELETE FROM files WHERE id = ?", (file_id,))

    def reconcile(self) -> Reconciled:
        keys = set(self.blobs.keys())
        rows = self.list()
        missing = [f for f in rows if f.path not in keys]
        with self.store.tx() as db:
            db.executemany("UPDATE files SET status = 'missing' WHERE id = ?", [(f.id,) for f in missing])
        known = {f.path for f in rows}
        unregistered = sorted(keys - known)
        by_hash = {hashlib.sha256(self.blobs.get(k)).hexdigest(): k for k in unregistered}
        suggestions = {f.id: by_hash[f.sha256] for f in missing if f.sha256 in by_hash}
        return Reconciled(
            missing=[f.model_copy(update={"status": "missing"}) for f in missing],
            unregistered=unregistered,
            suggestions=suggestions,
        )

    def relink(self, file_id: str, path: str) -> StoredFile:
        """Attach a (missing) file's id and metadata to the bytes now at ``path``."""
        file = self.by_id(file_id)
        path = self.clean(path)
        other = self._row("path = ?", path)
        if other is not None and other.id != file_id:
            raise FileError(409, f"{path} is already registered as file {other.id}")
        try:
            data = self.blobs.get(path)
        except FileNotFoundError as exc:
            raise FileError(404, f"nothing stored at {path}") from exc
        with self.store.tx() as db:
            db.execute("UPDATE files SET path = ? WHERE id = ?", (path, file_id))
        return self.put(path, data, mode="overwrite", role=file.role, deck_id=file.deck_id, mime=file.mime)
