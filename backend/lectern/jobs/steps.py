"""The job pipeline's pure steps: probing before triage, and the words of each verdict."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from lectern.agents.spec import AgentSpec
from lectern.jobs.fusion import Fusion, Outcome
from lectern.jobs.research import Context
from lectern.jobs.triage import Probes, Triage, probe
from lectern.models import Answer, SourceReport

NAMES = {"K": "the deck", "M": "past answers", "W": "the web", "P": "the model's own knowledge"}


def probes_for(ctx: Context, spec: AgentSpec, env: Mapping[str, str]) -> Probes:
    """The cheap signals: the question against the deck's text and against past questions."""
    deck = ctx.deck
    docs = [f"{s.title}\n{s.body}\n{s.notes}" for s in deck.slides]
    docs += [c.text for c in ctx.rows.store.chunks(deck.id or 0)]
    if ctx.dna is not None:
        docs += [f"{i.title}\n{i.body}" for i in ctx.dna.list(deck.id or 0, slide=ctx.slide)]
    memory = [j.question for j in ctx.rows.answered(deck.id or 0)]
    return probe(ctx.question, docs, memory, spec, ctx.provider.name, env)


def checked(sources: Sequence[SourceReport]) -> str:
    """ "the deck (nothing matched); skipped the web (no key)" — what was looked at and why not more."""
    looked = [f"{NAMES[s.source]} ({s.reason or 'no answer'})" for s in sources if s.status != "skipped"]
    passed = [f"{NAMES[s.source]} ({s.reason})" for s in sources if s.status == "skipped"]
    parts = []
    if looked:
        parts.append("I checked " + ", ".join(looked))
    if passed:
        parts.append("skipped " + ", ".join(passed))
    return "; ".join(parts) or "No source was consulted"


def abstain_text(triage: Triage, sources: Sequence[SourceReport], why: str) -> str:
    ghost = triage.coverage.get("ghost", 0)
    lead = f"I can't answer this from the sources I have: {why}."
    tail = (
        f" Triage rated it a likely ghost (P = {ghost:.2f}): no source is likely to hold the answer."
        if triage.kind == "ghost"
        else ""
    )
    return f"{lead} {checked(sources)}.{tail}"


def ask_text(question: str) -> str:
    return (
        f'Could you say a bit more about "{question}"? For example, which figure, claim or part of '
        "this slide you mean."
    )


def qualified(answer: Answer, why: str) -> Answer:
    return answer.model_copy(update={"answer": f"(Not certain: {why}.) {answer.answer}"})


def confidence(
    triage: Triage, fusion: Fusion | None, outcome: Outcome, sources: Sequence[SourceReport]
) -> dict[str, Any]:
    """What the answer's confidence chips show: per source, fused, and how triage saw it."""
    return {
        "verdict": outcome.verdict,
        "why": outcome.why,
        "triage": {
            "by": triage.by,
            "class": triage.kind,
            "coverage": triage.coverage,
            "engage": triage.engage,
            "hops": triage.hops,
            "note": triage.note,
            "ambiguity": triage.ambiguity,
            "probes": triage.probes,
            "system1": triage.system1,
        },
        "fusion": fusion.public() if fusion else None,
        "sources": [
            {"source": s.source, "status": s.status, "r": s.r, "g": s.g, "reason": s.reason} for s in sources
        ],
    }
