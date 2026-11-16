"""System1: the fast decision model behind triage, resolved from what the owner already configured.

Resolution order (decision D9):

a. **Explicit:** ``SYSTEM1_MODEL_PROVIDER`` (openrouter | openai | google | anthropic | openai_compat)
   with ``SYSTEM1_API_KEY``, ``SYSTEM1_MODEL_NAME`` and optionally ``SYSTEM1_BASE_URL``.
b. **The main provider is OpenRouter** (``LECTERN_PROVIDER=openrouter``, or a base URL on
   openrouter.ai, which is also ``openai_compat``'s default): jev on OpenRouter's decisions endpoint
   with ``LECTERN_API_KEY``, unless ``SYSTEM1_MODEL_NAME`` names another ``provider/model``.
   ``OPENROUTER_API_KEY``, when set, also enables jev.
c. **OpenAI, Google or Anthropic:** none of them has a decisions endpoint, so a *structured System1*
   runs on the same provider and key: a small model (``SYSTEM1_MODEL_NAME``, else ``LECTERN_MODEL``)
   whose JSON output mirrors jev's ``noul``/``choice`` answers (OpenAI ``response_format``
   json_schema, Gemini ``responseSchema``, Anthropic forced tool use).
d. Otherwise, the rules.

Only variable **names** are kept; a key is read from the environment when the call is made.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from lectern.http import Http

JEV_MODEL = "typesafe/jev-1.13-20260917"
OPENROUTER = "https://openrouter.ai/api/v1"
BASES = {
    "openai": "https://api.openai.com/v1",
    "openrouter": OPENROUTER,
    "anthropic": "https://api.anthropic.com",
    "google": "https://generativelanguage.googleapis.com/v1beta",
}
HOSTS = {
    "openrouter.ai": "openrouter",
    "api.openai.com": "openai",
    "api.anthropic.com": "anthropic",
    "generativelanguage.googleapis.com": "google",
}
TIMEOUT_S = 8.0


@dataclass(frozen=True)
class System1:
    kind: str  # jev | structured | rules
    provider: str | None = None
    model: str | None = None
    key_env: str | None = None
    base_url: str | None = None
    why: str = ""

    @property
    def label(self) -> str:
        return self.kind if self.kind != "structured" else f"structured:{self.provider}"

    def public(self, env: Mapping[str, str]) -> dict[str, Any]:
        key = "set" if self.key_env and env.get(self.key_env) else "unset"
        return {
            "kind": self.kind,
            "provider": self.provider,
            "model": self.model,
            "key_env": self.key_env,
            "key": key,
            "base_url": self.base_url,
            "why": self.why,
        }


def main_provider(env: Mapping[str, str]) -> str | None:
    """The main model's provider family, from ``LECTERN_PROVIDER`` and the base URL's host."""
    kind = env.get("LECTERN_PROVIDER", "fake")
    if kind in ("openrouter", "anthropic", "openai", "google"):
        return kind
    if kind == "openai_compat":
        host = urlparse(env.get("LECTERN_BASE_URL") or OPENROUTER).hostname or ""
        return HOSTS.get(host, "openai_compat")
    return None


def resolve_system1(env: Mapping[str, str]) -> System1:
    named = env.get("SYSTEM1_MODEL_NAME") or None
    explicit = env.get("SYSTEM1_MODEL_PROVIDER")
    if explicit:
        return pick(
            explicit,
            named,
            "SYSTEM1_API_KEY",
            env.get("SYSTEM1_BASE_URL"),
            env,
            "SYSTEM1_MODEL_PROVIDER is set",
        )
    main = main_provider(env)
    if main == "openrouter" and env.get("LECTERN_API_KEY"):
        return pick("openrouter", named, "LECTERN_API_KEY", None, env, "the main provider is OpenRouter")
    if env.get("OPENROUTER_API_KEY"):
        return System1(
            "jev",
            "openrouter",
            env.get("LECTERN_JEV_MODEL") or JEV_MODEL,
            "OPENROUTER_API_KEY",
            OPENROUTER,
            "OPENROUTER_API_KEY is set",
        )
    if main in ("openai", "google", "anthropic", "openai_compat") and env.get("LECTERN_API_KEY"):
        model = named or env.get("LECTERN_MODEL")
        base = env.get("LECTERN_BASE_URL") or None
        return pick(
            main, model, "LECTERN_API_KEY", base, env, f"structured System1 on the main provider ({main})"
        )
    return System1("rules", why="no System1 key or provider configured")


def pick(
    provider: str, model: str | None, key_env: str, base: str | None, env: Mapping[str, str], why: str
) -> System1:
    if not env.get(key_env):
        return System1("rules", provider, model, key_env, base, f"{why}, but {key_env} is unset")
    if provider == "openrouter" and (model is None or model.startswith("typesafe/jev")):
        return System1(
            "jev",
            provider,
            model or env.get("LECTERN_JEV_MODEL") or JEV_MODEL,
            key_env,
            base or OPENROUTER,
            f"{why}: jev on OpenRouter's decisions endpoint",
        )
    if not model:
        return System1("rules", provider, None, key_env, base, f"{why}, but no model is named")
    return System1("structured", provider, model, key_env, base or BASES.get(provider), why)


def schema(questions: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """The answers' JSON schema: ``{qid: {noul: p}}`` and ``{coverage: {choice, confidence}}``."""
    props: dict[str, Any] = {}
    for qid, q in questions.items():
        if q["type"] == "noul":
            inner = {"noul": {"type": "number", "minimum": 0, "maximum": 1}}
        else:
            inner = {
                "choice": {"type": "string", "enum": list(q["criteria"])},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            }
        props[qid] = {
            "type": "object",
            "properties": inner,
            "required": list(inner),
            "additionalProperties": False,
        }
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def without_extras(node: Any) -> Any:
    """Gemini's responseSchema is an OpenAPI subset: no additionalProperties."""
    if isinstance(node, dict):
        return {k: without_extras(v) for k, v in node.items() if k != "additionalProperties"}
    return node


def structured_answers(
    s1: System1, state: Mapping[str, Any], questions: Mapping[str, Any], env: Mapping[str, str], http: Http
) -> dict[str, Any]:
    """Ask a small model for jev-shaped answers as JSON, through its provider's structured output."""
    key, shape = env.get(s1.key_env or "", ""), schema(questions)
    body: dict[str, Any]
    prompt = (
        "You are System1, a fast triage step. Before any source is searched, answer each question about "
        "the user's question as a probability (noul: 0 false, 1 true) or one option with a confidence.\n"
        f"State: {json.dumps(state)}\nQuestions: {json.dumps(questions)}"
    )
    if s1.provider == "anthropic":
        body = {
            "model": s1.model,
            "max_tokens": 800,
            "messages": [{"role": "user", "content": prompt}],
            "tools": [{"name": "system1", "description": "Record the answers.", "input_schema": shape}],
            "tool_choice": {"type": "tool", "name": "system1"},
        }
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
        reply = http.post_json(f"{s1.base_url}/v1/messages", body, headers, TIMEOUT_S)
        return dict(next(b["input"] for b in reply["content"] if b.get("type") == "tool_use"))
    if s1.provider == "google":
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": without_extras(shape),
            },
        }
        url = f"{s1.base_url}/models/{s1.model}:generateContent"
        reply = http.post_json(url, body, {"x-goog-api-key": key}, TIMEOUT_S)
        return dict(json.loads(reply["candidates"][0]["content"]["parts"][0]["text"]))
    body = {
        "model": s1.model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "system1", "strict": True, "schema": shape},
        },
    }
    reply = http.post_json(
        f"{s1.base_url}/chat/completions", body, {"Authorization": f"Bearer {key}"}, TIMEOUT_S
    )
    return dict(json.loads(reply["choices"][0]["message"]["content"]))
