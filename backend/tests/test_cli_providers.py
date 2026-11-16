"""The CLI, and the provider factory and real providers (with httpx stubbed: no network)."""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx
import pytest
from conftest import FIXTURES, REPO

from lectern import cli
from lectern.graph.state import Block
from lectern.providers.anthropic import AnthropicProvider
from lectern.providers.base import get_provider, render_blocks
from lectern.providers.fake import FakeProvider
from lectern.providers.openai_compat import OpenAICompatProvider


def test_cli_seed_ingest_attach_ask(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    monkeypatch.setenv("LECTERN_DB", str(tmp_path / "cli.db"))
    monkeypatch.delenv("LECTERN_PROVIDER", raising=False)
    assert cli.main(["seed", str(REPO / "decks")]) == 0
    out = capsys.readouterr().out
    assert "seeded 3 decks" in out and "+ kettle-quarterly-review.data.csv" in out
    assert cli.main(["ingest", str(FIXTURES / "artifact.html")]) == 0
    assert cli.main(["attach", "4", str(REPO / "decks" / "kettle-quarterly-review.data.csv")]) == 0
    assert cli.main(["ask", "4", "1", "What is the intro?"]) == 0
    out = capsys.readouterr().out
    assert "slide-1: " in out and "cites: slide:1:" in out
    assert cli.main(["ask", "4", "99", "q"]) == 1
    bad = tmp_path / "bad.bin"
    bad.write_bytes(b"\x00")
    assert cli.main(["ingest", str(bad)]) == 1
    assert cli.main(["attach", "1", str(bad)]) == 2


def test_get_provider() -> None:
    assert isinstance(get_provider({}), FakeProvider)
    assert isinstance(
        get_provider({"LECTERN_PROVIDER": "anthropic", "LECTERN_API_KEY": "k", "LECTERN_MODEL": "m"}),
        AnthropicProvider,
    )
    compat = get_provider({"LECTERN_PROVIDER": "openai_compat", "LECTERN_API_KEY": "k", "LECTERN_MODEL": "m"})
    assert isinstance(compat, OpenAICompatProvider)
    with pytest.raises(ValueError, match="LECTERN_API_KEY must be set"):
        get_provider({"LECTERN_PROVIDER": "anthropic"})
    with pytest.raises(ValueError, match="unknown LECTERN_PROVIDER"):
        get_provider({"LECTERN_PROVIDER": "magic"})


def test_fake_provider_edge_cases() -> None:
    fake = FakeProvider()
    assert fake.complete("", [], "q") == "There is nothing on this slide to answer from."
    blocks: Sequence[Block] = [Block("slide:1:title", "Hello. World!"), Block("slide:1:body", "Other")]
    assert (
        fake.complete("", blocks, "zzz")
        == "Hello. [slide:1:title] World! [slide:1:title] Other [slide:1:body]"
    )
    repeated = [
        Block("slide:2:title", "Plan"),
        Block("slide:3:body", "Plan"),
        Block("deck:outline", "2. Plan"),
    ]
    assert fake.complete("", repeated, "plan on slide 2") == "Plan [slide:2:title] 2. Plan [deck:outline]"
    assert render_blocks(blocks) == "[slide:1:title]\nHello. World!\n\n[slide:1:body]\nOther"


class Captured:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append((url, kwargs))
        return httpx.Response(200, json=self.payload, request=httpx.Request("POST", url))


def test_anthropic_request_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = Captured({"content": [{"type": "text", "text": " Hi [slide:1:title] "}]})
    monkeypatch.setattr(httpx, "post", fake.post)
    provider = AnthropicProvider(api_key="k", model="m")
    assert provider.complete("persona", [Block("slide:1:title", "T")], "q") == "Hi [slide:1:title]"
    url, kwargs = fake.calls[0]
    assert url == "https://api.anthropic.com/v1/messages"
    assert kwargs["headers"]["x-api-key"] == "k" and kwargs["timeout"] == 60.0
    assert kwargs["json"]["model"] == "m" and "[slide:1:title]\nT" in kwargs["json"]["messages"][0]["content"]


def test_openai_compat_request_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = Captured({"choices": [{"message": {"content": "Yes [deck:outline]"}}]})
    monkeypatch.setattr(httpx, "post", fake.post)
    provider = OpenAICompatProvider(api_key="k", model="m", base_url="http://local/v1")
    assert provider.complete("p", [Block("deck:outline", "1. A")], "q") == "Yes [deck:outline]"
    url, kwargs = fake.calls[0]
    assert url == "http://local/v1/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer k"
    monkeypatch.setattr(httpx, "post", Captured({"choices": []}).post)
    assert provider.complete("p", [], "q") == ""
