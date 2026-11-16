"""Decision D1: the file registry, blob stores and folder decks."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest

from lectern import folders
from lectern.blobs import BadPath, LocalBlobs, MemoryBlobs, S3Blobs, blobs_from_env, clean_path
from lectern.files import FileError, Files
from lectern.store import Store


@pytest.fixture
def files(store: Store) -> Files:
    return Files(store, MemoryBlobs())


def test_paths_are_clean_and_relative() -> None:
    assert clean_path("./decks//q3/01.html") == "decks/q3/01.html"
    for bad in ("", "/etc/passwd", "../x", "a/../../b", "a\x00b", "x" * 301):
        with pytest.raises(BadPath):
            clean_path(bad)


def test_create_overwrite_keeps_id_and_metadata(files: Files) -> None:
    a = files.put("refs/memo.txt", b"v1", mode="create", meta={"title": "Memo"})
    assert (a.version, a.status, a.mime, a.size) == (1, "live", "text/plain", 2)
    with pytest.raises(FileError) as conflict:
        files.put("refs/memo.txt", b"again", mode="create")
    assert conflict.value.status == 409
    with pytest.raises(FileError) as missing:
        files.put("refs/nope.txt", b"x", mode="overwrite")
    assert missing.value.status == 404
    b = files.put("refs/memo.txt", b"v2", mode="overwrite")
    assert b.id == a.id and b.version == 2 and b.meta == {"title": "Memo"}
    assert files.put("refs/memo.txt", b"v2").version == 2  # the same bytes are not a new version
    assert files.read("refs/memo.txt")[1] == b"v2" and files.text(a.id) == "v2"
    assert files.update_meta("refs/memo.txt", {"title": None, "order": 3}).meta == {"order": 3}
    with pytest.raises(FileError) as big:
        files.put("refs/big.bin", b"x" * (20 * 1024 * 1024 + 1))
    assert big.value.status == 413


def test_move_delete_reconcile_relink_and_forget(files: Files) -> None:
    memo = files.put("refs/memo.txt", b"board memo")
    moved = files.move("refs/memo.txt", "refs/2026/memo.txt")
    assert moved.id == memo.id and moved.version == 1 and files.blobs.keys() == ["refs/2026/memo.txt"]
    with pytest.raises(FileError):
        files.move("refs/2026/memo.txt", "refs/2026/memo.txt")
    # Someone renames the blob outside lectern, and adds another file lectern never saw.
    files.blobs.put("archive/memo-final.txt", files.blobs.get("refs/2026/memo.txt"))
    files.blobs.delete("refs/2026/memo.txt")
    files.blobs.put("archive/other.txt", b"something else")
    found = files.reconcile()
    assert [f.id for f in found.missing] == [memo.id] and files.by_id(memo.id).status == "missing"
    assert found.unregistered == ["archive/memo-final.txt", "archive/other.txt"]
    assert found.suggestions == {memo.id: "archive/memo-final.txt"}
    with pytest.raises(FileError) as gone:
        files.read("refs/2026/memo.txt")
    assert gone.value.status == 410
    relinked = files.relink(memo.id, "archive/memo-final.txt")
    assert relinked.id == memo.id and relinked.status == "live" and relinked.version == 1
    other = files.put("archive/other.txt", b"something else")
    with pytest.raises(FileError):
        files.relink(memo.id, "archive/other.txt")
    deleted = files.delete("archive/other.txt")
    assert deleted.status == "missing" and files.by_id(other.id).status == "missing"
    files.purge(other.id)
    with pytest.raises(FileError):
        files.by_id(other.id)
    files.delete("archive/memo-final.txt", purge=True)
    assert files.list() == []


def test_folder_decks_one_file_per_slide(store: Store, files: Files) -> None:
    deck, intro = folders.put_slide(store, files, "decks/q3/02-plan.md", b"# Plan\nHire a barista.")
    deck, _ = folders.put_slide(
        store,
        files,
        "decks/q3/01-intro.html",
        b"<h1>Intro</h1><p>Hello</p><img src='x.png'>",
        meta={"notes": "Say hi", "deck_title": "Q3 review"},
    )
    assert deck.title == "q3" and deck.source == "folder" and deck.folder == "decks/q3"
    assert [(s.n, s.title) for s in deck.slides] == [(1, "Intro"), (2, "Plan")]
    assert deck.slides[0].notes == "Say hi" and 'data-lectern-id="img-1"' in (deck.slides[0].html or "")
    assert deck.slide_ref(deck.slides[1]) == intro.id and "1. Intro" in deck.outline
    files.update_meta("decks/q3/02-plan.md", {"order": 0})
    deck = folders.rebuild(store, files, deck.id or 0)
    assert [s.title for s in deck.slides] == ["Plan", "Intro"]
    files.delete("decks/q3/02-plan.md")
    assert [s.title for s in folders.rebuild(store, files, deck.id or 0).slides] == ["Intro"]
    with pytest.raises(Exception, match="deck folder"):
        folders.put_slide(store, files, "loose.html", b"<h1>x</h1>")


def test_local_blobs(tmp_path: Path) -> None:
    blobs = LocalBlobs(tmp_path / "b")
    assert blobs.keys() == []
    blobs.put("decks/q3/a.html", b"A")
    assert blobs.get("decks/q3/a.html") == b"A" and blobs.keys("decks/") == ["decks/q3/a.html"]
    blobs.delete("decks/q3/a.html")
    blobs.delete("decks/q3/a.html")  # deleting twice is fine
    with pytest.raises(FileNotFoundError):
        blobs.get("decks/q3/a.html")
    assert isinstance(blobs_from_env({"LECTERN_BLOBS": str(tmp_path / "c")}), LocalBlobs)


class FakeS3:
    """The four boto3 calls S3Blobs uses, with pagination."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(self, Bucket: str, Key: str, Body: bytes) -> None:
        self.objects[f"{Bucket}/{Key}"] = Body

    def get_object(self, Bucket: str, Key: str) -> dict[str, Any]:
        if f"{Bucket}/{Key}" not in self.objects:
            raise KeyError("NoSuchKey")
        return {"Body": io.BytesIO(self.objects[f"{Bucket}/{Key}"])}

    def delete_object(self, Bucket: str, Key: str) -> None:
        self.objects.pop(f"{Bucket}/{Key}", None)

    def list_objects_v2(self, Bucket: str, Prefix: str, ContinuationToken: str = "0") -> dict[str, Any]:
        keys = sorted(k[len(Bucket) + 1 :] for k in self.objects if k.startswith(f"{Bucket}/{Prefix}"))
        start = int(ContinuationToken)
        page = {"Contents": [{"Key": k} for k in keys[start : start + 2]]}
        return page | ({"NextContinuationToken": str(start + 2)} if start + 2 < len(keys) else {})


def test_s3_blobs_with_a_fake_client() -> None:
    s3 = S3Blobs("bucket", "lectern/", client=FakeS3())
    for key in ("a/1.txt", "a/2.txt", "b/3.txt"):
        s3.put(key, key.encode())
    assert s3.keys() == ["a/1.txt", "a/2.txt", "b/3.txt"] and s3.keys("a/") == ["a/1.txt", "a/2.txt"]
    assert s3.get("b/3.txt") == b"b/3.txt" and "bucket/lectern/b/3.txt" in s3.client.objects
    s3.delete("b/3.txt")
    with pytest.raises(FileNotFoundError):
        s3.get("b/3.txt")
