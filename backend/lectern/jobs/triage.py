"""Triage: before any source is searched, decide whether to engage, where to look and where not to.

From the question and cheap probes (deck hits, memory hits, recency words) triage returns the
hurdle ``engage`` = P(engage), a route (consult or skip, with a reason, for each source P, W, K,
M), a coverage class (``covered | rare | ghost``, with probabilities), the estimated hops and
how ambiguous the question is.

Two implementations: ``rules`` (offline, the default and what tests use) and ``jev`` over
OpenRouter's decisions endpoint, used when ``OPENROUTER_API_KEY`` is set and the spec says
``auto`` or ``jev``. Any jev error falls back to the rules, and the trace says which one ran.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from lectern.agents.spec import AgentSpec
from lectern.http import RETRY_ONCE, Http, HttpStatusError
from lectern.jobs.system1 import resolve_system1, structured_answers
from lectern.models import SourceName
from lectern.search import bm25, tokenize

JEV_URL = "https://openrouter.ai/api/alpha/decisions"
JEV_TIMEOUT_S = 8.0
MAX_STATE_BYTES = 2048
RECENCY = re.compile(
    r"\b(today|latest|current(ly)?|now|recent(ly)?|this (week|month|year)|news|20[2-3]\d)\b", re.I
)
STOP = set(
    "a an and are as at be did do does for from had has have how i in is it its me my of on or so that the "
    "their them there these they this to was we were what when where which who why will with you your".split()
)
SOURCES: tuple[SourceName, ...] = ("K", "M", "W", "P")


@dataclass(frozen=True)
class Probes:
    """Cheap signals gathered before triage: no source has been searched yet."""

    k_score: float  # best BM25 score of the question against the deck (slides, notes, data, DNA)
    m_hits: int  # past answered questions that share terms with this one
    recency: bool
    content_terms: int
    tools: tuple[str, ...]
    model: str
    w_ready: bool  # web tools enabled and a key set


@dataclass(frozen=True)
class Triage:
    engage: float
    route: dict[SourceName, str | None]  # None: consult; otherwise why it is skipped
    coverage: dict[str, float]  # covered | rare | ghost
    hops: int
    ambiguity: float
    by: str = "rules"
    note: str = ""
    probes: dict[str, Any] = field(default_factory=dict)
    system1: dict[str, Any] = field(default_factory=dict)  # which System1 was resolved, and why

    @property
    def consult(self) -> tuple[SourceName, ...]:
        return tuple(s for s in SOURCES if self.route.get(s) is None)

    @property
    def kind(self) -> str:
        return max(self.coverage, key=lambda k: self.coverage[k])

    def public(self) -> dict[str, Any]:
        return asdict(self) | {"consult": list(self.consult), "class": self.kind}


def coverage_of(k_norm: float, m_hits: int, recency: bool) -> dict[str, float]:
    if k_norm >= 0.5 and not recency:
        return {"covered": 0.8, "rare": 0.15, "ghost": 0.05}
    if k_norm > 0 or m_hits or recency:
        return {"covered": 0.2, "rare": 0.65, "ghost": 0.15}
    return {"covered": 0.05, "rare": 0.25, "ghost": 0.7}


def rules(p: Probes) -> Triage:
    """The offline triage: keyword and probe heuristics."""
    k_norm = p.k_score / (p.k_score + 2)
    coverage = coverage_of(k_norm, p.m_hits, p.recency)
    covered = coverage["covered"] >= 0.5
    tools = set(p.tools)
    route: dict[SourceName, str | None] = {
        "K": None if tools & {"deck_search", "dna_search"} else "tool not enabled",
        "M": None
        if p.m_hits and "memory_search" in tools
        else ("no similar past question" if p.m_hits == 0 else "tool not enabled"),
        "W": web_route(p, covered),
        "P": "the fake model has no knowledge of its own"
        if p.model == "fake"
        else ("K holds the answer; the model is not needed" if covered else None),
    }
    ambiguity = 0.8 if p.content_terms <= 1 else 0.1
    engage = 0.1 if p.content_terms == 0 else 0.95
    return Triage(engage, route, coverage, 0 if covered else 1, ambiguity, probes=asdict(p))


def web_route(p: Probes, covered: bool) -> str | None:
    if "web_search" not in p.tools:
        return "tool not enabled"
    if not p.w_ready:
        return "skipped: no key"
    if covered:
        return "K holds the answer; W is unnecessary"
    return None


def probe(
    question: str,
    deck_docs: list[str],
    memory_docs: list[str],
    spec: AgentSpec,
    model: str,
    env: Mapping[str, str],
) -> Probes:
    terms = [t for t in tokenize(question) if t not in STOP]
    k_scores = bm25(question, deck_docs) if deck_docs else []
    m_scores = bm25(question, memory_docs) if memory_docs else []
    return Probes(
        k_score=round(max(k_scores, default=0.0), 4),
        m_hits=sum(1 for s in m_scores if s > 0),
        recency=bool(RECENCY.search(question)),
        content_terms=len(terms),
        tools=tuple(spec.tools),
        model=model,
        w_ready=bool(env.get("EXA_API_KEY")),
    )


def triage(question: str, p: Probes, spec: AgentSpec, env: Mapping[str, str], http: Http) -> Triage:
    """The System1 the owner configured (jev, or a structured model) when it answers; the rules otherwise."""
    s1 = resolve_system1(env)
    base = replace(rules(p), system1=s1.public(env))
    if spec.triage.provider == "rules" or s1.kind == "rules":
        return base
    retrying = RetryOnce(http)
    try:
        if s1.kind == "jev":
            body = {"state": jev_state(question, p), "model": s1.model, "questions": JEV_QUESTIONS}
            key = env.get(s1.key_env or "", "")
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "X-Title": "lectern",
            }
            answers = retrying.post_json(JEV_URL, body, headers, JEV_TIMEOUT_S)["answers"]
        else:
            answers = structured_answers(s1, jev_state(question, p), JEV_QUESTIONS, env, retrying)
        return from_answers(base, answers, s1.label)
    except HttpStatusError as exc:
        # A 422 means lectern sent a bad request: a bug to surface, not just an outage.
        bug = " (request bug: lectern sent an invalid request)" if exc.status == 422 else ""
        return replace(base, note=f"{s1.label} failed (HTTP {exc.status}){bug}; used rules")
    except Exception as exc:  # timeouts, transport errors, unusable answers: all fall back
        return replace(base, note=f"{s1.label} failed ({type(exc).__name__}); used rules")


def jev_state(question: str, p: Probes) -> dict[str, Any]:
    state = {"question": question[:600], "probes": asdict(p)}
    if len(json.dumps(state).encode()) > MAX_STATE_BYTES:
        state["question"] = question[:200]
    return state


def noul(instructions: str, true: str, false: str) -> dict[str, Any]:
    return {"type": "noul", "instructions": instructions, "criteria": {"true": true, "false": false}}


SOURCE_NAMES = {
    "K": "the deck, its notes and its DNA",
    "W": "the open web",
    "P": "the model's own knowledge",
    "M": "lectern's past answers on this deck",
}
JEV_QUESTIONS: dict[str, dict[str, Any]] = {
    "engage": noul(
        "Is this a well-posed, in-scope question worth answering?",
        "well-posed and in scope",
        "out of scope, ill-posed or resting on a false premise",
    ),
    **{
        f"consult_{s}": noul(
            f"Is {name} likely to hold the answer?", "likely holds it", "unlikely to hold it"
        )
        for s, name in SOURCE_NAMES.items()
    },
    "coverage": {
        "type": "choice",
        "instructions": "How well do the available sources cover this question?",
        "criteria": {
            "covered": "a source almost surely holds the answer",
            "rare": "a source may hold it",
            "ghost": "no source is likely to hold it",
        },
    },
    "ambiguous": noul(
        "Is the question ambiguous enough to need a clarifying question first?",
        "needs clarifying",
        "clear enough to answer",
    ),
}
COVERAGE = ("covered", "rare", "ghost")


class JevUnusable(ValueError):
    """An answer that is missing, out of range or not one of the options."""


def noul_of(answers: dict[str, Any], qid: str) -> float:
    value = (answers.get(qid) or {}).get("noul")
    if not isinstance(value, int | float) or isinstance(value, bool) or not 0 <= value <= 1:
        raise JevUnusable(f"{qid}: noul {value!r} is not in [0, 1]")
    return float(value)


def coverage_from(answer: Any) -> dict[str, float]:
    choice, conf = (answer or {}).get("choice"), (answer or {}).get("confidence", 0.8)
    if choice not in COVERAGE or not isinstance(conf, int | float) or not 0 <= conf <= 1:
        raise JevUnusable(f"coverage: {answer!r}")
    return {c: (float(conf) if c == choice else (1 - float(conf)) / 2) for c in COVERAGE}


def from_answers(base: Triage, answers: Mapping[str, Any], by: str) -> Triage:
    """jev-shaped answers (from jev or a structured System1) applied to the rules' triage."""
    prob = {qid: noul_of(dict(answers), qid) for qid, q in JEV_QUESTIONS.items() if q["type"] == "noul"}
    route = dict(
        base.route
    )  # System1 may only narrow the rules' route: it cannot enable a missing tool or key
    for s in SOURCES:
        if route[s] is None and prob[f"consult_{s}"] < 0.3:
            route[s] = f"{by}: unlikely to hold the answer (p={prob[f'consult_{s}']:.2f})"
    coverage = coverage_from(answers.get("coverage"))
    return replace(
        base, engage=prob["engage"], route=route, coverage=coverage, ambiguity=prob["ambiguous"], by=by
    )


class RetryOnce:
    """The http port, with 429 and 529 (rate limited, overloaded) retried once."""

    def __init__(self, http: Http) -> None:
        self.http = http

    def post_json(
        self, url: str, body: Mapping[str, Any], headers: Mapping[str, str], timeout: float
    ) -> dict[str, Any]:
        try:
            return self.http.post_json(url, body, headers, timeout)
        except HttpStatusError as exc:
            if exc.status not in RETRY_ONCE:
                raise
            return self.http.post_json(url, body, headers, timeout)

    def get_text(self, url: str, timeout: float) -> str:
        return self.http.get_text(url, timeout)
