"""Where file contents live: a local folder (the default) or S3 / any S3-compatible store.

Only bytes go here. Everything else about a file (its permanent id, path, version, hash and
metadata) is a row in SQLite (``files.py``). Keys are the files' relative paths, so the bucket or
folder stays readable to people, and a file renamed outside lectern can be found again
(``reconcile``).

Choose with ``LECTERN_BLOBS``: a folder path (default ``lectern-blobs``) or ``s3://bucket/prefix``.
S3 needs the optional extra (``uv sync --extra s3`` or ``pip install lectern[s3]``) and the usual
AWS environment (``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY``, ``AWS_REGION``, and
``AWS_ENDPOINT_URL`` for MinIO or R2).
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

MAX_PATH = 300
SAFE_PATH = re.compile(r"^[\w.\- ()/]+$")


class BadPath(ValueError):
    """A path that is not a clean relative path (no ``..``, no leading ``/``, safe characters)."""


def clean_path(path: str) -> str:
    """The canonical form of a relative file path, or ``BadPath``."""
    path = path.strip().replace("\\", "/")
    parts = PurePosixPath(path).parts
    if not path or len(path) > MAX_PATH or path.startswith("/") or ".." in parts or not SAFE_PATH.match(path):
        raise BadPath(f"not a clean relative path: {path!r}")
    return "/".join(p for p in parts if p not in ("", "."))


class BlobStore(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def keys(self, prefix: str = "") -> list[str]: ...


class MemoryBlobs:
    """Blobs in a dict: for tests and throwaway apps."""

    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}

    def put(self, key: str, data: bytes) -> None:
        self.data[clean_path(key)] = data

    def get(self, key: str) -> bytes:
        try:
            return self.data[clean_path(key)]
        except KeyError as exc:
            raise FileNotFoundError(key) from exc

    def delete(self, key: str) -> None:
        self.data.pop(clean_path(key), None)

    def keys(self, prefix: str = "") -> list[str]:
        return sorted(k for k in self.data if k.startswith(prefix))


class LocalBlobs:
    """Files under one folder, at their relative paths."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        full = (self.root / clean_path(key)).resolve()
        if self.root not in full.parents:
            raise BadPath(key)
        return full

    def put(self, key: str, data: bytes) -> None:
        full = self._path(key)
        full.parent.mkdir(parents=True, exist_ok=True)
        tmp = full.with_name(full.name + ".part")
        tmp.write_bytes(data)
        tmp.replace(full)  # a reader never sees half a file

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def keys(self, prefix: str = "") -> list[str]:
        if not self.root.exists():
            return []
        found = (p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file())
        return sorted(k for k in found if k.startswith(prefix) and not k.endswith(".part"))


class S3Blobs:
    """An S3 bucket (or MinIO, R2 …) under an optional key prefix. ``client`` is a boto3 S3 client."""

    def __init__(self, bucket: str, prefix: str = "", client: Any = None) -> None:
        if client is None:
            import boto3  # type: ignore[import-not-found, import-untyped, unused-ignore]  # optional extra: lectern[s3]

            client = boto3.client("s3")
        self.bucket, self.prefix, self.client = bucket, prefix.strip("/"), client

    def _key(self, key: str) -> str:
        key = clean_path(key)
        return f"{self.prefix}/{key}" if self.prefix else key

    def put(self, key: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=self._key(key), Body=data)

    def get(self, key: str) -> bytes:
        try:
            body = self.client.get_object(Bucket=self.bucket, Key=self._key(key))["Body"]
        except Exception as exc:  # boto3's NoSuchKey; normalise to what LocalBlobs raises
            raise FileNotFoundError(key) from exc
        return bytes(body.read())

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self._key(key))

    def keys(self, prefix: str = "") -> list[str]:
        start = self._key(prefix) if prefix else self.prefix
        cut = len(self.prefix) + 1 if self.prefix else 0
        out: list[str] = []
        token: str | None = None
        while True:
            extra = {"ContinuationToken": token} if token else {}
            page = self.client.list_objects_v2(Bucket=self.bucket, Prefix=start, **extra)
            out += [obj["Key"][cut:] for obj in page.get("Contents", [])]
            token = page.get("NextContinuationToken")
            if not token:
                return sorted(out)


def blobs_from_env(env: Mapping[str, str] | None = None) -> BlobStore:
    env = os.environ if env is None else env
    where = env.get("LECTERN_BLOBS", "lectern-blobs")
    if where.startswith("s3://"):
        bucket, _, prefix = where[5:].partition("/")
        return S3Blobs(bucket, prefix)
    return LocalBlobs(where)
