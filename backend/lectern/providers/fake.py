"""The default provider: extractive and deterministic, so tests can assert exact answers.

It splits every block into sentences (dropping repeats), ranks them with BM25 against the
question, keeps the top three (in rank order; ties keep context order) and puts each one's block
id after it as a marker. Slide references such as "slide 4" are left out of the ranking: the
``route`` node has already used them. When nothing matches it quotes the first three sentences
of the context. The same input always gives the same bytes.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from lectern.graph.state import Block
from lectern.search import top_k

TOP = 3
_SENTENCE = re.compile(r"(?<=[A-Za-z%)][.!?])\s+(?=[A-Z])|\n+")  # "4. Plan" (an outline line) stays whole
_SLIDE_REF = re.compile(r"\bslides?\s*#?\s*\d+", re.IGNORECASE)


def sentences(blocks: Sequence[Block]) -> list[tuple[str, str]]:
    """``(sentence, block id)`` pairs in context order; a repeated sentence keeps its first block."""
    seen: dict[str, str] = {}
    for block in blocks:
        for part in _SENTENCE.split(block.text):
            if part.strip():
                seen.setdefault(part.strip(), block.id)
    return list(seen.items())


class FakeProvider:
    """No model at all: BM25 picks the sentences."""

    name = "fake"

    def complete(self, system: str, blocks: Sequence[Block], question: str) -> str:
        pairs = sentences(blocks)
        if not pairs:
            return "There is nothing on this slide to answer from."
        query = _SLIDE_REF.sub(" ", question)
        picked = top_k(query, [s for s, _ in pairs], TOP) or list(range(min(TOP, len(pairs))))
        return " ".join(f"{pairs[i][0]} [{pairs[i][1]}]" for i in picked)
