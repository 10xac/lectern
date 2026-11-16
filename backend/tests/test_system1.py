"""Decision D9: System1 resolves from what is configured; every branch runs offline with fakes."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest
from test_confidence import PROBES, SPEC, jev_answers

from lectern.jobs.system1 import resolve_system1
from lectern.jobs.triage import JEV_URL, triage

KEY = "test-sentinel-key-not-real"
OWNER = {
    "LECTERN_PROVIDER": "openai_compat",
    "LECTERN_BASE_URL": "https://openrouter.ai/api/v1",
    "LECTERN_API_KEY": KEY,
}


@pytest.mark.parametrize(
    ("env", "kind", "provider", "key_env", "model"),
    [
        (OWNER, "jev", "openrouter", "LECTERN_API_KEY", "typesafe/jev-1.13-20260917"),
        (
            OWNER | {"SYSTEM1_MODEL_NAME": "openai/gpt-mini"},
            "structured",
            "openrouter",
            "LECTERN_API_KEY",
            "openai/gpt-mini",
        ),
        (
            {"LECTERN_PROVIDER": "openai_compat", "LECTERN_API_KEY": KEY},
            "jev",
            "openrouter",
            "LECTERN_API_KEY",
            None,
        ),
        ({"OPENROUTER_API_KEY": KEY}, "jev", "openrouter", "OPENROUTER_API_KEY", None),
        (
            {"SYSTEM1_MODEL_PROVIDER": "openai", "SYSTEM1_API_KEY": KEY, "SYSTEM1_MODEL_NAME": "small"}
            | OWNER,
            "structured",
            "openai",
            "SYSTEM1_API_KEY",
            "small",
        ),
        (
            {"SYSTEM1_MODEL_PROVIDER": "google", "SYSTEM1_MODEL_NAME": "flash"},
            "rules",
            "google",
            "SYSTEM1_API_KEY",
            None,
        ),
        ({"SYSTEM1_MODEL_PROVIDER": "anthropic", "SYSTEM1_API_KEY": KEY}, "rules", "anthropic", None, None),
        (
            {"LECTERN_PROVIDER": "anthropic", "LECTERN_API_KEY": KEY, "LECTERN_MODEL": "haiku"},
            "structured",
            "anthropic",
            None,
            "haiku",
        ),
        (
            {
                "LECTERN_PROVIDER": "openai_compat",
                "LECTERN_BASE_URL": "https://api.openai.com/v1",
                "LECTERN_API_KEY": KEY,
                "LECTERN_MODEL": "m",
            },
            "structured",
            "openai",
            None,
            "m",
        ),
        (
            {
                "LECTERN_PROVIDER": "openai_compat",
                "LECTERN_BASE_URL": "https://generativelanguage.googleapis.com/v1beta",
                "LECTERN_API_KEY": KEY,
                "LECTERN_MODEL": "g",
            },
            "structured",
            "google",
            None,
            "g",
        ),
        (
            {
                "LECTERN_PROVIDER": "openai_compat",
                "LECTERN_BASE_URL": "http://localhost:11434/v1",
                "LECTERN_API_KEY": KEY,
                "LECTERN_MODEL": "local",
            },
            "structured",
            "openai_compat",
            None,
            "local",
        ),
        ({}, "rules", None, None, None),
    ],
)
def test_resolution_order(
    env: dict[str, str], kind: str, provider: str | None, key_env: str | None, model: str | None
) -> None:
    s1 = resolve_system1(env)
    assert (s1.kind, s1.provider) == (kind, provider), s1.why
    assert key_env is None or s1.key_env == key_env
    assert model is None or s1.model == model
    assert KEY not in json.dumps(s1.public(env)) and s1.why


class Fake:
    """Answers each provider in its own shape, and remembers the requests."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any], Mapping[str, str]]] = []

    def post_json(
        self, url: str, body: Mapping[str, Any], headers: Mapping[str, str], timeout: float
    ) -> dict[str, Any]:
        self.calls.append((url, dict(body), headers))
        answers = jev_answers()
        if url == JEV_URL:
            return {"answers": answers}
        if url.endswith("/v1/messages"):
            return {"content": [{"type": "text", "text": "ok"}, {"type": "tool_use", "input": answers}]}
        if ":generateContent" in url:
            return {"candidates": [{"content": {"parts": [{"text": json.dumps(answers)}]}}]}
        return {"choices": [{"message": {"content": json.dumps(answers)}}]}

    def get_text(self, url: str, timeout: float) -> str:
        return ""


@pytest.mark.parametrize(
    ("env", "by", "check"),
    [
        (OWNER, "jev", lambda url, body, h: url == JEV_URL and h["Authorization"] == f"Bearer {KEY}"),
        (
            OWNER | {"SYSTEM1_MODEL_NAME": "openai/gpt-mini"},
            "structured:openrouter",
            lambda url, body, h: (
                url.endswith("openrouter.ai/api/v1/chat/completions")
                and body["response_format"]["json_schema"]["strict"] is True
            ),
        ),
        (
            {"LECTERN_PROVIDER": "anthropic", "LECTERN_API_KEY": KEY, "LECTERN_MODEL": "haiku"},
            "structured:anthropic",
            lambda url, body, h: (
                body["tool_choice"] == {"type": "tool", "name": "system1"} and h["x-api-key"] == KEY
            ),
        ),
        (
            {"SYSTEM1_MODEL_PROVIDER": "google", "SYSTEM1_API_KEY": KEY, "SYSTEM1_MODEL_NAME": "flash"},
            "structured:google",
            lambda url, body, h: (
                url.endswith("/models/flash:generateContent")
                and "additionalProperties" not in json.dumps(body["generationConfig"]["responseSchema"])
            ),
        ),
    ],
)
def test_each_system1_runs_and_reports_itself(env: dict[str, str], by: str, check: Any) -> None:
    http = Fake()
    got = triage("What changed today?", PROBES, SPEC, env, http)
    assert got.by == by and got.kind == "ghost" and got.system1["key"] == "set", got.note
    assert check(*http.calls[0]) and KEY not in json.dumps(got.public())


def test_unusable_structured_output_falls_back_to_rules() -> None:
    class Broken(Fake):
        def post_json(
            self, url: str, body: Mapping[str, Any], headers: Mapping[str, str], timeout: float
        ) -> dict[str, Any]:
            return {"choices": [{"message": {"content": "not json"}}]}

    env = {
        "LECTERN_PROVIDER": "openai_compat",
        "LECTERN_BASE_URL": "https://api.openai.com/v1",
        "LECTERN_API_KEY": KEY,
        "LECTERN_MODEL": "m",
    }
    got = triage("q", PROBES, SPEC, env, Broken())
    assert got.by == "rules" and got.note == "structured:openai failed (JSONDecodeError); used rules"
