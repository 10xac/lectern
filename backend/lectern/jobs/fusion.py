"""Fuse per-source answers into one, two ways, and decide: answer, qualify, ask or abstain.

Candidates are the sources' answers clustered by normalised text and word overlap, plus the outside option
``NONE`` ("none of these": what a source that found nothing votes for).

* **Bayesian:** ``p(y|e) ∝ p0(y) ∏_s [(1-g_s)(r_s p_s(y) + (1-r_s) u(y)) + g_s u(y)]``, with
  ``u`` uniform, ``p0(∅)`` triage's ghost probability (the rest spread evenly) and ``p_s`` a
  point mass on source s's answer. The evidence ``Z`` (the normaliser) is reported.
* **Dempster-Shafer:** simple support functions ``m_s({ŷ_s}) = r_s``, ``m_s(Θ) = 1 - r_s``,
  combined by Dempster's rule. The total conflict ``κ`` is reported, never just absorbed.

See ``docs/confidence.md`` for worked examples.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from math import prod
from typing import Any, Literal

from lectern.agents.spec import Decision
from lectern.models import SourceReport

NONE = "∅"
CONFLICT_QUALIFY = 0.5  # sources that clash this much qualify the answer, whatever the posterior
_MARKER = re.compile(r"\[[a-z]+(?::[\w.-]+)+\]")
Verdict = Literal["answer", "qualify", "ask", "abstain"]


def normalise(text: str) -> str:
    """The cluster key of an answer: no citation markers, no punctuation, lower case."""
    words = re.sub(r"[^\w\s]", " ", _MARKER.sub(" ", text)).lower().split()
    return " ".join(words) or NONE


SAME = 0.5  # answers sharing at least half their content words are one candidate


def cluster(keys: dict[str, str]) -> dict[str, str]:
    """Merge paraphrases: each answer joins the first earlier one whose content words mostly match
    (Jaccard ≥ ``SAME``), so two extracts of the same fact are not counted as a conflict."""
    out: dict[str, str] = {}
    for source, key in keys.items():
        words = set(key.split())
        same = (
            k
            for k in dict.fromkeys(out.values())
            if k != NONE and key != NONE and len(words & set(k.split())) >= SAME * len(words | set(k.split()))
        )
        out[source] = next(same, key)
    return out


@dataclass(frozen=True)
class Fusion:
    candidates: list[str]  # cluster keys; the last one is NONE
    labels: dict[str, str]  # cluster key → a readable answer (the first source's text)
    votes: dict[str, str]  # source → cluster key
    bayes: dict[str, float]
    z: float
    ds: dict[str, float]  # mass on each singleton after combination; "Θ" is what is left uncommitted
    kappa: float

    @property
    def best(self) -> str:
        return max(self.bayes, key=lambda k: (self.bayes[k], k != NONE))

    def public(self) -> dict[str, Any]:
        label = self.labels.get
        return {
            "best": label(self.best, self.best),
            "p_best": round(self.bayes[self.best], 4),
            "bayes": {label(k, k): round(v, 4) for k, v in self.bayes.items()},
            "z": round(self.z, 6),
            "ds": {label(k, k): round(v, 4) for k, v in self.ds.items()},
            "kappa": round(self.kappa, 4),
            "votes": self.votes,
        }


def fuse(reports: Sequence[SourceReport], p_none: float | None = None) -> Fusion:
    """Fuse the done sources' answers. ``p_none`` is the prior on "none of these" (triage's ghost
    probability); the rest of the prior is spread evenly over the candidates. ``None``: all uniform."""
    voters = [r for r in reports if r.status == "done"]
    votes = cluster({r.source: normalise(r.answer) for r in voters})
    labels = {votes[r.source]: r.answer for r in reversed(voters)}
    candidates = [*sorted({v for v in votes.values() if v != NONE}), NONE]
    bayes, z = bayesian(voters, votes, candidates, p_none)
    ds, kappa = dempster_shafer(voters, votes, candidates)
    sources = [r for r in voters if r.source != "M"]
    if sources:  # past answers are conversation, not a source: their disagreement is not a conflict
        _, kappa = dempster_shafer(sources, votes, candidates)
    return Fusion(candidates, labels, votes, bayes, z, ds, kappa)


def bayesian(
    voters: Sequence[SourceReport], votes: dict[str, str], candidates: list[str], p_none: float | None = None
) -> tuple[dict[str, float], float]:
    u = 1 / len(candidates)
    others = len(candidates) - 1
    if p_none is None or others == 0:
        p0 = dict.fromkeys(candidates, u)
    else:
        p0 = {y: (p_none if y == NONE else (1 - p_none) / others) for y in candidates}

    def likelihood(y: str, s: SourceReport) -> float:
        p_s = 1.0 if votes[s.source] == y else 0.0
        return (1 - s.g) * (s.r * p_s + (1 - s.r) * u) + s.g * u

    raw = {y: p0[y] * prod(likelihood(y, s) for s in voters) for y in candidates}
    z = sum(raw.values())
    return {y: v / z for y, v in raw.items()}, z


def dempster_shafer(
    voters: Sequence[SourceReport], votes: dict[str, str], candidates: list[str]
) -> tuple[dict[str, float], float]:
    theta = frozenset(candidates)
    mass: dict[frozenset[str], float] = {theta: 1.0}
    agree = 1.0  # the product of (1 - κ_i) over the pairwise combinations
    for s in voters:
        focal = {frozenset({votes[s.source]}): s.r, theta: 1 - s.r}
        combined: dict[frozenset[str], float] = {}
        conflict = 0.0
        for a, ma in mass.items():
            for b, mb in focal.items():
                both = a & b
                if both:
                    combined[both] = combined.get(both, 0.0) + ma * mb
                else:
                    conflict += ma * mb
        if conflict >= 1.0:  # total conflict: Dempster's rule is undefined; keep what we had
            return {**{y: mass.get(frozenset({y}), 0.0) for y in candidates}, "Θ": mass.get(theta, 0.0)}, 1.0
        mass = {k: v / (1 - conflict) for k, v in combined.items()}
        agree *= 1 - conflict
    out = {y: mass.get(frozenset({y}), 0.0) for y in candidates}
    return {**out, "Θ": mass.get(theta, 0.0)}, 1 - agree


@dataclass(frozen=True)
class Outcome:
    verdict: Verdict
    why: str
    details: dict[str, Any] = field(default_factory=dict)


def decide(fusion: Fusion, rules: Decision, ambiguity: float) -> Outcome:
    """Answer above ``answer_at``; qualify within the band or under heavy conflict; else ask or abstain."""
    p = fusion.bayes[fusion.best]
    if rules.ask_when == "ambiguous" and ambiguity >= 0.5:
        return Outcome("ask", "the question is ambiguous")
    if fusion.best == NONE:
        return Outcome("abstain", "no source holds the answer")
    if fusion.kappa >= CONFLICT_QUALIFY:
        return Outcome("qualify", f"sources disagree (κ = {fusion.kappa:.2f})")
    if abs(p - rules.answer_at) <= rules.qualify_band:
        return Outcome("qualify", f"confidence is borderline (P = {p:.2f})")
    if p > rules.answer_at:
        return Outcome("answer", f"P = {p:.2f}")
    return Outcome("abstain", f"confidence too low (P = {p:.2f})")
