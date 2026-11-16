"""Anthropic Messages API over ``httpx`` (no SDK). Never used in tests.

Env: ``LECTERN_API_KEY``, ``LECTERN_MODEL``; optional ``LECTERN_BASE_URL``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import httpx

from lectern.graph.state import Block
from lectern.providers.base import CITE_RULE, render_blocks, require

API_VERSION = "2023-06-01"
TIMEOUT_S = 60.0


@dataclass(frozen=True)
class AnthropicProvider:
    api_key: str = field(repr=False)  # never printed, logged or traced
    model: str
    base_url: str = "https://api.anthropic.com"
    max_tokens: int = 800
    name: str = "anthropic"

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> AnthropicProvider:
        base = env.get("LECTERN_BASE_URL") or cls.base_url
        key, model = require(env, "LECTERN_API_KEY"), require(env, "LECTERN_MODEL")
        return cls(api_key=key, model=model, base_url=base)

    def complete(self, system: str, blocks: Sequence[Block], question: str) -> str:
        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": f"{system}\n\n{CITE_RULE}",
            "messages": [{"role": "user", "content": f"{render_blocks(blocks)}\n\nQuestion: {question}"}],
        }
        headers = {"x-api-key": self.api_key, "anthropic-version": API_VERSION}
        resp = httpx.post(f"{self.base_url}/v1/messages", json=body, headers=headers, timeout=TIMEOUT_S)
        resp.raise_for_status()
        parts = resp.json().get("content", [])
        return "".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()
