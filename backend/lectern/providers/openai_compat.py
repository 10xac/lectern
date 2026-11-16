"""Any OpenAI-compatible chat completions API (OpenRouter and similar) over ``httpx``.
Never used in tests.

Env: ``LECTERN_API_KEY``, ``LECTERN_MODEL``; optional ``LECTERN_BASE_URL``
(default ``https://openrouter.ai/api/v1``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import httpx

from lectern.graph.state import Block
from lectern.providers.base import CITE_RULE, render_blocks, require

TIMEOUT_S = 60.0


@dataclass(frozen=True)
class OpenAICompatProvider:
    api_key: str = field(repr=False)  # never printed, logged or traced
    model: str
    base_url: str = "https://openrouter.ai/api/v1"
    name: str = "openai_compat"

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> OpenAICompatProvider:
        base = env.get("LECTERN_BASE_URL") or cls.base_url
        key, model = require(env, "LECTERN_API_KEY"), require(env, "LECTERN_MODEL")
        return cls(api_key=key, model=model, base_url=base)

    def complete(self, system: str, blocks: Sequence[Block], question: str) -> str:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": f"{system}\n\n{CITE_RULE}"},
                {"role": "user", "content": f"{render_blocks(blocks)}\n\nQuestion: {question}"},
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        resp = httpx.post(f"{self.base_url}/chat/completions", json=body, headers=headers, timeout=TIMEOUT_S)
        resp.raise_for_status()
        choices = resp.json().get("choices", [])
        return str(choices[0]["message"]["content"]).strip() if choices else ""
