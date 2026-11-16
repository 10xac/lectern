"""AC-P0: AgentSpec layers, request overrides, per-instance models and keys that never leak."""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Sequence
from pathlib import Path

import pytest
from conftest import FIXTURES, FakeClock
from fastapi.testclient import TestClient

from lectern.agents import resolve
from lectern.agents.spec import ModelBinding, RequestAgent, SpecError, deep_merge
from lectern.api import create_app
from lectern.graph.state import Block
from lectern.ingest.html_artifact import parse
from lectern.models import Deck, IngestError
from lectern.providers.anthropic import AnthropicProvider
from lectern.providers.base import Provider, provider_for
from lectern.providers.fake import FakeProvider
from lectern.store import Store

SENTINEL = "test-sentinel-key-not-real"


class Recording:
    """A fake provider that remembers which binding and persona each call used."""

    def __init__(self, binding: ModelBinding, calls: list[tuple[str | None, str]]) -> None:
        self.binding, self.calls, self.name = binding, calls, "fake"

    def complete(self, system: str, blocks: Sequence[Block], question: str) -> str:
        self.calls.append((self.binding.model, system.split("\n\n")[0]))
        return FakeProvider().complete(system, blocks, question)


def client_with(calls: list[tuple[str | None, str]]) -> tuple[TestClient, int]:
    def factory(binding: ModelBinding) -> Provider:
        return Recording(binding, calls)

    client = TestClient(create_app(Store(), clock=FakeClock(), providers=factory))
    html = (FIXTURES / "artifact.html").read_bytes()
    deck = client.post("/decks", files={"file": ("artifact.html", html)}).json()
    return client, deck["id"]


def test_layers_merge_in_order_and_unknown_keys_are_422() -> None:
    calls: list[tuple[str | None, str]] = []
    client, d = client_with(calls)
    assert client.put(
        f"/decks/{d}/agent", json={"persona": "Deck voice", "budget": {"max_seconds": 30}}
    ).is_success
    got = client.put(f"/decks/{d}/slides/2/agent", json={"persona": "Slide voice"}).json()
    assert got["spec"]["persona"] == "Slide voice" and got["spec"]["budget"]["max_seconds"] == 30
    assert got["spec"]["budget"]["max_researchers"] == 4  # deep merge keeps the default's siblings
    assert got["layers"]["persona"] == "slide" and got["layers"]["budget"] == "deck"
    assert got["layers"]["tools"] == "default"
    one = client.get(f"/agents/resolve?deck={d}&slide=1").json()
    assert one["spec"]["persona"] == "Deck voice" and one["layers"]["persona"] == "deck"
    bad = client.put(f"/decks/{d}/slides/2/agent", json={"budget": {"max_secs": 1}})
    assert bad.status_code == 422 and "max_secs" in bad.text
    assert client.put(f"/decks/{d}/agent", json={"colour": "red"}).status_code == 422
    assert client.get(f"/agents/resolve?deck={d}&slide=9").status_code == 404
    ask = {"question": "q", "agent": {"temperature": 1}}
    assert client.post(f"/decks/{d}/slides/1/ask", json=ask).status_code == 422


def test_two_slides_answer_with_different_personas_and_models() -> None:
    calls: list[tuple[str | None, str]] = []
    client, d = client_with(calls)
    client.put(f"/decks/{d}/slides/1/agent", json={"persona": "Voice A", "model": {"model": "m-a"}})
    client.put(f"/decks/{d}/slides/2/agent", json={"persona": "Voice B", "model": {"model": "m-b"}})
    for n in (1, 2):
        assert client.post(
            f"/decks/{d}/slides/{n}/ask?wait=true",
            json={"question": "What is the intro text inside this group?"},
        ).is_success
    assert [c for c in calls if c[1].startswith("Voice")] == [("m-a", "Voice A"), ("m-b", "Voice B")]
    assert {c[0] for c in calls} == {"m-a", "m-b"}  # the researchers used their own instance's model too


def test_request_override_may_only_narrow(monkeypatch: pytest.MonkeyPatch) -> None:
    deck = parse((FIXTURES / "artifact.html").read_bytes())
    deck = deck.model_copy(update={"agent": {"tools": ["deck_search", "dna_search"]}})
    with pytest.raises(SpecError, match="web_search"):
        resolve(deck, 1, RequestAgent.model_validate({"tools": ["deck_search", "web_search"]}))
    with pytest.raises(SpecError, match="max_tool_calls"):
        resolve(deck, 1, RequestAgent.model_validate({"budget": {"max_tool_calls": 99}}))
    with pytest.raises(SpecError, match="ALLOWLIST"):
        resolve(
            deck, 1, RequestAgent.model_validate({"model": {"provider": "anthropic", "model": "big"}}), {}
        )
    lower = resolve(
        deck, 1, RequestAgent.model_validate({"tools": ["dna_search"], "budget": {"max_seconds": 5}})
    )
    assert lower.spec.tools == ["dna_search"] and lower.spec.budget.max_seconds == 5
    assert lower.layers["tools"] == "request"
    env = {"LECTERN_MODEL_ALLOWLIST": "anthropic:big, openai_compat:small"}
    picked = resolve(
        deck, 1, RequestAgent.model_validate({"model": {"provider": "anthropic", "model": "big"}}), env
    )
    assert picked.spec.model.provider == "anthropic" and picked.spec.model.api_key_env is None


def test_a_request_never_carries_one_providers_key_to_another() -> None:
    deck = Deck(
        title="t", source="html", agent={"model": {"provider": "anthropic", "model": "a", "api_key_env": "K"}}
    )
    env = {"LECTERN_MODEL_ALLOWLIST": "openai_compat:o,anthropic:b"}
    other = resolve(
        deck, None, RequestAgent.model_validate({"model": {"provider": "openai_compat", "model": "o"}}), env
    )
    same = resolve(
        deck, None, RequestAgent.model_validate({"model": {"provider": "anthropic", "model": "b"}}), env
    )
    assert other.spec.model.api_key_env is None and same.spec.model.api_key_env == "K"
    assert resolve(deck, None).spec.id == "deck"


def test_keys_never_appear_in_responses_traces_or_logs(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    monkeypatch.setenv("MY_KEY", SENTINEL)
    calls: list[tuple[str | None, str]] = []
    client, d = client_with(calls)
    layer = {"model": {"provider": "anthropic", "model": "claude-x", "api_key_env": "MY_KEY"}}
    stored = client.put(f"/decks/{d}/agent", json=layer)
    assert stored.json()["spec"]["model"]["key"] == "set"
    resolved = client.get(f"/agents/resolve?deck={d}&slide=1")
    answer = client.post(
        f"/decks/{d}/slides/1/ask?wait=true", json={"question": "What is the intro text inside this group?"}
    )
    trace = client.get(f"/traces/{answer.json()['answer']['trace_id']}")
    events = client.get(f"/jobs/{answer.json()['id']}/events")
    deck = client.get(f"/decks/{d}")
    for resp in (stored, resolved, answer, trace, deck, events):
        assert SENTINEL not in resp.text
    assert SENTINEL not in caplog.text
    built = provider_for(ModelBinding.model_validate(layer["model"]))
    assert isinstance(built, AnthropicProvider) and built.api_key == SENTINEL
    assert SENTINEL not in repr(built)
    monkeypatch.delenv("MY_KEY")
    assert client.get(f"/agents/resolve?deck={d}").json()["spec"]["model"]["key"] == "unset"


def test_provider_for_and_the_env_layer() -> None:
    assert isinstance(provider_for(ModelBinding()), FakeProvider)
    with pytest.raises(ValueError, match=r"model\.model"):
        provider_for(ModelBinding(provider="openai_compat"))
    with pytest.raises(ValueError, match="LECTERN_API_KEY"):
        provider_for(ModelBinding(provider="openai_compat", model="m"), {})
    deck = Deck(title="t", source="html")
    env = {"LECTERN_PROVIDER": "openai_compat", "LECTERN_MODEL": "m", "LECTERN_BASE_URL": "http://x"}
    got = resolve(deck, None, env=env)
    assert got.spec.model.base_url == "http://x" and got.layers["model"] == "env"
    assert deep_merge({"a": {"b": 1, "c": 2}, "l": [1]}, {"a": {"b": 3}, "l": [2]}) == {
        "a": {"b": 3, "c": 2},
        "l": [2],
    }


def test_html_data_agent_and_migration(tmp_path: Path) -> None:
    html = b'<section data-agent=\'{"persona": "From markup"}\'><h1>A</h1></section>'
    deck = parse(html + b"<section><h1>B</h1></section>")
    assert deck.slides[0].agent == {"persona": "From markup"} and deck.slides[1].agent is None
    with pytest.raises(IngestError, match="slide 1: data-agent is not valid JSON"):
        parse(b"<section data-agent='{oops'><h1>A</h1></section>")
    with pytest.raises(IngestError, match="JSON object"):
        parse(b"<section data-agent='[1]'><h1>A</h1></section>")
    old = tmp_path / "v01.db"  # a v0.1 database without the agent columns
    with sqlite3.connect(old) as db:
        db.execute(
            "CREATE TABLE decks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, source TEXT NOT NULL,"
            " persona TEXT, outline TEXT NOT NULL DEFAULT '')"
        )
        db.execute("INSERT INTO decks (title, source) VALUES ('old', 'html')")
    store = Store(old)
    Store(old)  # migrating twice is a no-op
    assert store.get_deck(1) == Deck(id=1, title="old", source="html")
