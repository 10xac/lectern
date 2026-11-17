"""Semantic citation verification via NLI (``pip install lectern[nli]``).

Checks whether each (claim, cited-block) pair is entailment or not. Citations scoring
contradiction or neutral are stripped. Optional: ``NLIChecker.available()`` is ``False``
when the library is absent.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

MARKER = re.compile(r"\[([a-z]+(?::[\w.-]+)+)\]")
DEFAULT_MODEL = "cross-encoder/nli-deberta-v3-small"


def _try_import() -> Any:
    try:
        from transformers import pipeline
        return pipeline
    except ImportError:
        return None


class NLIChecker:
    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self._model_name, self._pipe = model_name, None

    @staticmethod
    def available() -> bool:
        return _try_import() is not None

    def _load(self) -> Any:
        if self._pipe is None:
            factory = _try_import()
            if factory is None:
                raise ImportError("pip install lectern[nli]")
            self._pipe = factory("text-classification", model=self._model_name)
        return self._pipe

    def check_batch(self, pairs: Sequence[tuple[str, str]]) -> list[str]:
        pipe = self._load()
        inputs = [f"{ev} [SEP] {cl}" for cl, ev in pairs]
        return [str(r["label"]).lower() for r in pipe(inputs, truncation=True, batch_size=len(inputs))]


def extract_claims(answer: str) -> list[tuple[str, str]]:
    """Split answer into ``(claim_text, block_id)`` pairs from citation markers."""
    claims, parts = [], MARKER.split(answer)
    for i in range(0, len(parts) - 1, 2):
        text = parts[i].strip().rstrip(".,;:!?").strip()
        if text:
            claims.append((text, parts[i + 1]))
    return claims


def verify_citations(
    checker: Any, answer: str, blocks: dict[str, str],
) -> tuple[str, list[str]]:
    """Verify citations; strip those scoring contradiction/neutral. Returns (cleaned, kept_ids)."""
    claims = extract_claims(answer)
    if not claims:
        return answer, list(MARKER.findall(answer))
    pairs = [(c, blocks[b]) for c, b in claims if b in blocks]
    if not pairs:
        return answer, list(MARKER.findall(answer))
    verdicts = checker.check_batch(pairs)
    keep, remove = set[str](), set[str]()
    for (_, bid), v in zip(((c, b) for c, b in claims if b in blocks), verdicts):
        (keep if v == "entailment" else remove).add(bid)
    cleaned = answer
    for bid in remove - keep:
        cleaned = cleaned.replace(f"[{bid}]", "")
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned, [b for b in MARKER.findall(cleaned) if b in keep or b not in blocks]
