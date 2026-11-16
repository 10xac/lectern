"""What a model provider is, and how to pick one from the environment.

``complete(system, blocks, question)`` returns the answer text, with a ``[block-id]`` marker
after each sentence that uses a block. The ``cite`` node keeps only markers that name a block
that was really in the context.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import Protocol

from lectern.agents.spec import DEFAULT_KEY_ENV, ModelBinding
from lectern.graph.state import Block

CITE_RULE = (
    "Answer only from the context blocks below. After each sentence, cite the block it came from "
    "as [block-id], using the ids exactly as given. If the blocks do not answer the question, say so."
)


class Provider(Protocol):
    """A model that answers a question from context blocks."""

    @property
    def name(self) -> str: ...

    def complete(self, system: str, blocks: Sequence[Block], question: str) -> str: ...


def render_blocks(blocks: Sequence[Block]) -> str:
    """The context as the real providers send it: one ``[id]`` header per block."""
    return "\n\n".join(f"[{b.id}]\n{b.text}" for b in blocks)


def get_provider(env: Mapping[str, str] | None = None) -> Provider:
    """``LECTERN_PROVIDER`` = ``fake`` (the default), ``anthropic`` or ``openai_compat``."""
    env = os.environ if env is None else env
    kind = env.get("LECTERN_PROVIDER", "fake")
    if kind == "fake":
        from lectern.providers.fake import FakeProvider

        return FakeProvider()
    if kind == "anthropic":
        from lectern.providers.anthropic import AnthropicProvider

        return AnthropicProvider.from_env(env)
    if kind == "openai_compat":
        from lectern.providers.openai_compat import OpenAICompatProvider

        return OpenAICompatProvider.from_env(env)
    raise ValueError(f"unknown LECTERN_PROVIDER {kind!r} (fake | anthropic | openai_compat)")


def provider_for(binding: ModelBinding, env: Mapping[str, str] | None = None) -> Provider:
    """The provider for one agent instance. Its key is read from ``binding.api_key_env`` now."""
    env = os.environ if env is None else env
    if binding.provider == "fake":
        from lectern.providers.fake import FakeProvider

        return FakeProvider()
    from lectern.providers.anthropic import AnthropicProvider
    from lectern.providers.openai_compat import OpenAICompatProvider

    if not binding.model:
        raise ValueError(f"the {binding.provider} provider needs model.model")
    key = require(env, binding.api_key_env or DEFAULT_KEY_ENV)
    if binding.provider == "anthropic":
        default = AnthropicProvider.base_url
        return AnthropicProvider(api_key=key, model=binding.model, base_url=binding.base_url or default)
    default = OpenAICompatProvider.base_url
    return OpenAICompatProvider(api_key=key, model=binding.model, base_url=binding.base_url or default)


def require(env: Mapping[str, str], key: str) -> str:
    value = env.get(key, "")
    if not value:
        raise ValueError(f"{key} must be set for this provider (see .env.example)")
    return value
