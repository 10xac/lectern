"""The ``AgentSpec``: the one document that defines an agent, and how its layers merge.

Layers apply in order: the packaged default (``default.json``), then ``env`` (the
``LECTERN_PROVIDER``/``LECTERN_MODEL`` settings v0.1 used), then the deck, then the slide, then the
request. The first four are free-form JSON objects that are deep-merged and validated as a whole, so
an unknown key anywhere is refused. The request layer is narrower (``RequestAgent``): it may change
the persona, pick a model from ``LECTERN_MODEL_ALLOWLIST``, keep a subset of the tools and lower
the budget, nothing else.

Keys are never part of a spec: ``model.api_key_env`` names the environment variable to read, and
``public`` shows only whether it is set.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from functools import cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ContextKind = Literal["slide", "notes", "neighbours", "deck_outline", "dna", "attachments"]
ToolName = Literal["deck_search", "dna_search", "memory_search", "web_search", "fetch_url"]
ProviderKind = Literal["fake", "anthropic", "openai_compat"]
DEFAULT_KEY_ENV = "LECTERN_API_KEY"


class SpecError(ValueError):
    """A layer or a request override that is not allowed (the API answers 422)."""


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Decision(Strict):
    answer_at: float = Field(default=0.5, ge=0, le=1)
    qualify_band: float = Field(default=0.15, ge=0, le=0.5)
    ask_when: Literal["ambiguous", "never"] = "ambiguous"


class Behaviour(Strict):
    rules: list[str] = Field(default_factory=list)
    decision: Decision = Decision()


class ModelBinding(Strict):
    provider: ProviderKind = "fake"
    model: str | None = None
    api_key_env: str | None = None  # the variable's name; the key itself never enters a spec
    base_url: str | None = None


class Triage(Strict):
    provider: Literal["auto", "rules", "jev"] = "auto"  # auto: jev when OPENROUTER_API_KEY is set


class Budget(Strict):
    max_researchers: int = Field(default=4, ge=1, le=16)
    max_seconds: float = Field(default=60, gt=0, le=600)
    max_tool_calls: int = Field(default=12, ge=0, le=100)


class AgentSpec(Strict):
    id: str
    persona: str
    behaviour: Behaviour = Behaviour()
    context: list[ContextKind]
    model: ModelBinding = ModelBinding()
    tools: list[ToolName]
    triage: Triage = Triage()
    budget: Budget = Budget()


class RequestModel(Strict):
    provider: ProviderKind
    model: str | None = None


class RequestBudget(Strict):
    max_researchers: int | None = Field(None, ge=1)
    max_seconds: float | None = Field(None, gt=0)
    max_tool_calls: int | None = Field(None, ge=0)


class RequestAgent(Strict):
    """What one question may change about the agent that answers it."""

    persona: str | None = Field(None, max_length=2000)
    model: RequestModel | None = None
    tools: list[ToolName] | None = None
    budget: RequestBudget | None = None


class Resolved(BaseModel):
    """An effective spec and, for each top-level field, the layer that last set it."""

    spec: AgentSpec
    layers: dict[str, str]

    def public(self, env: Mapping[str, str] | None = None) -> dict[str, Any]:
        """The spec as the API shows it: the key's variable name and whether it is set, never its value."""
        env = os.environ if env is None else env
        data = self.spec.model_dump()
        key_env = self.spec.model.api_key_env or DEFAULT_KEY_ENV
        data["model"]["key"] = "set" if env.get(key_env) else "unset"
        return {"spec": data, "layers": self.layers}


@cache
def packaged_default() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((Path(__file__).parent / "default.json").read_text("utf-8"))
    return data


def env_layer(env: Mapping[str, str]) -> dict[str, Any]:
    """v0.1's provider settings, so an existing ``.env`` keeps working."""
    kind = env.get("LECTERN_PROVIDER", "fake")
    if kind == "fake":
        return {}
    binding = {"provider": kind, "model": env.get("LECTERN_MODEL") or None, "api_key_env": DEFAULT_KEY_ENV}
    return {"model": binding | {"base_url": env.get("LECTERN_BASE_URL") or None}}


def deep_merge(base: Mapping[str, Any], over: Mapping[str, Any]) -> dict[str, Any]:
    """Objects merge key by key; anything else (lists included) is replaced."""
    out = dict(base)
    for key, value in over.items():
        old = out.get(key)
        out[key] = (
            deep_merge(old, value) if isinstance(old, Mapping) and isinstance(value, Mapping) else value
        )
    return out


def merge_layers(layers: Sequence[tuple[str, Mapping[str, Any] | None]]) -> Resolved:
    """Deep-merge the named layers in order and validate the result."""
    data: dict[str, Any] = {}
    origin: dict[str, str] = {}
    for name, layer in layers:
        if not layer:
            continue
        if not isinstance(layer, Mapping):
            raise SpecError(f"the {name} agent layer must be a JSON object")
        data = deep_merge(data, layer)
        origin.update(dict.fromkeys(layer, name))
    try:
        spec = AgentSpec.model_validate(data)
    except ValueError as exc:  # pydantic's ValidationError is a ValueError
        raise SpecError(str(exc)) from exc
    return Resolved(spec=spec, layers={key: origin.get(key, "default") for key in AgentSpec.model_fields})


def allowed_models(env: Mapping[str, str]) -> set[str]:
    raw = env.get("LECTERN_MODEL_ALLOWLIST", "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def apply_request(resolved: Resolved, req: RequestAgent | None, env: Mapping[str, str]) -> Resolved:
    """Apply a request override. It may narrow the agent, never widen it."""
    if req is None:
        return resolved
    spec, layers = resolved.spec, dict(resolved.layers)
    update: dict[str, Any] = {}
    if req.persona is not None:
        update["persona"] = req.persona
    if req.model is not None:
        name = f"{req.model.provider}:{req.model.model or ''}"
        if req.model.provider != "fake" and name not in allowed_models(env):
            raise SpecError(f"model {name!r} is not in LECTERN_MODEL_ALLOWLIST")
        # The key variable and base URL carry over only for the same provider: a request must not
        # send one provider's key to another.
        same = req.model.provider == spec.model.provider
        update["model"] = ModelBinding(
            provider=req.model.provider,
            model=req.model.model,
            api_key_env=spec.model.api_key_env if same else None,
            base_url=spec.model.base_url if same else None,
        )
    if req.tools is not None:
        extra = sorted(set(req.tools) - set(spec.tools))
        if extra:
            raise SpecError(f"tools {extra} are not enabled for this deck")
        update["tools"] = list(req.tools)
    if req.budget is not None:
        update["budget"] = lower_budget(spec.budget, req.budget)
    layers.update(dict.fromkeys(update, "request"))
    return Resolved(spec=spec.model_copy(update=update), layers=layers)


def lower_budget(current: Budget, req: RequestBudget) -> Budget:
    asked = req.model_dump(exclude_none=True)
    raised = sorted(k for k, v in asked.items() if v > getattr(current, k))
    if raised:
        raise SpecError(f"a request may only lower the budget; {raised} would rise")
    return current.model_copy(update=asked)
