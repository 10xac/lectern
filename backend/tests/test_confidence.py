"""AC-P2: triage, per-source confidence, Bayesian and Dempster-Shafer fusion, and the decision."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import pytest

from lectern.agents.spec import AgentSpec, Decision
from lectern.jobs.fusion import NONE, decide, fuse, normalise
from lectern.jobs.manager import JobManager
from lectern.jobs.triage import JEV_URL, MAX_STATE_BYTES, Probes, jev_state, rules, triage
from lectern.jobs.web import EXA_URL, agreement
from lectern.models import Deck, Job, SourceReport
from lectern.providers.fake import FakeProvider
from lectern.store import Store

WEB_TEXT = (
    "Harbour cafe prices rose in November because of a new ferry route. The ferry route doubled visitors."
)


class FakeHttp:
    """Exa and jev, offline. ``jev`` is an answer dict, or an exception to raise."""

    def __init__(self, jev: dict[str, Any] | Exception | None = None, text: str = WEB_TEXT) -> None:
        self.jev, self.text, self.calls = jev, text, []  # type: ignore[var-annotated]

    def post_json(
        self, url: str, body: Mapping[str, Any], headers: Mapping[str, str], timeout: float
    ) -> dict[str, Any]:
        self.calls.append((url, dict(body), timeout))
        if url == EXA_URL:
            hits = [
                {"url": f"https://news.example/{i}", "title": f"News {i}", "text": self.text}
                for i in range(3)
            ]
            return {"results": [{"url": "https://news.example/empty", "title": "Empty"}, *hits]}
        if isinstance(self.jev, Exception):
            raise self.jev
        return {"model": body["model"], "answers": self.jev, "usage": {}}

    def get_text(self, url: str, timeout: float) -> str:
        self.calls.append((url, {}, timeout))
        return self.text


def run_job(store: Store, deck: Deck, question: str, http: FakeHttp, n: int = 2) -> Job:
    jobs = JobManager(store, FakeProvider(), http=http)

    async def go() -> Job | None:
        return await jobs.wait(jobs.submit(deck, n, question).id)

    job = asyncio.run(go())
    assert job is not None and job.answer is not None and job.answer.confidence is not None
    return job


@pytest.fixture
def web_deck(store: Store, kettle: Deck, monkeypatch: pytest.MonkeyPatch) -> Deck:
    monkeypatch.setenv("EXA_API_KEY", "test-key")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    tools = ["deck_search", "dna_search", "memory_search", "web_search", "fetch_url"]
    store.set_agent(kettle.id or 0, None, {"tools": tools})
    deck = store.get_deck(kettle.id or 0)
    assert deck is not None
    return deck


def routes(job: Job) -> dict[str, str]:
    return {s.source: s.status for s in job.sources}


def test_covered_question_is_answered_from_k_and_w_is_skipped(store: Store, web_deck: Deck) -> None:
    http = FakeHttp()
    job = run_job(store, web_deck, "Why did the harbour cafe grow?", http)
    conf = job.answer.confidence  # type: ignore[union-attr]
    assert job.status == "answered" and conf["verdict"] == "answer" and conf["triage"]["class"] == "covered"
    assert routes(job)["K"] == "done" and routes(job)["W"] == "skipped"
    assert "W is unnecessary" in next(s.reason for s in job.sources if s.source == "W")
    assert http.calls == []  # the web was never touched
    assert conf["fusion"]["p_best"] > 0.5


def test_fresh_question_routes_to_w(store: Store, web_deck: Deck) -> None:
    http = FakeHttp()
    job = run_job(store, web_deck, "What are the latest harbour cafe prices this month?", http)
    assert routes(job)["W"] == "done"
    assert [c[0] for c in http.calls] == [EXA_URL, "https://news.example/empty"]  # search, then fetch_url
    w = next(s for s in job.sources if s.source == "W")
    assert w.tool_calls == 2 and w.r > 0.4 and "web:1" in w.block_ids


def test_ghost_question_abstains_and_names_the_ghost(store: Store, kettle: Deck) -> None:
    job = run_job(store, kettle, "Which chess grandmaster won the 1987 Dubai olympiad?", FakeHttp())
    assert job.status == "abstained" and job.answer is not None
    assert job.answer.confidence["triage"]["class"] == "ghost"  # type: ignore[index]
    assert "ghost" in job.answer.answer and "I checked the deck" in job.answer.answer
    assert job.answer.citations == []


def test_contradicting_k_and_w_give_high_kappa_and_qualify(store: Store, web_deck: Deck) -> None:
    job = run_job(store, web_deck, "Why is the harbour cafe growing right now?", FakeHttp())
    conf = job.answer.confidence  # type: ignore[union-attr]
    assert routes(job)["K"] == "done" and routes(job)["W"] == "done"
    assert conf["fusion"]["kappa"] >= 0.5 and conf["verdict"] == "qualify"
    assert job.status == "answered" and job.answer.answer.startswith("(Not certain: sources disagree")  # type: ignore[union-attr]


def test_ambiguous_and_out_of_scope_questions(store: Store, kettle: Deck) -> None:
    asked = run_job(store, kettle, "and the margins?", FakeHttp())
    assert asked.status == "asked" and "say a bit more" in asked.answer.answer  # type: ignore[union-attr]
    declined = run_job(store, kettle, "is it?", FakeHttp())
    assert declined.status == "abstained" and "out of scope" in declined.answer.answer  # type: ignore[union-attr]


SPEC = AgentSpec.model_validate(
    {"id": "t", "persona": "p", "context": [], "tools": ["deck_search", "web_search"]}
)
PROBES = Probes(
    k_score=0.5,
    m_hits=0,
    recency=True,
    content_terms=4,
    tools=("deck_search", "web_search"),
    model="fake",
    w_ready=True,
)


def jev_answers(**over: Any) -> dict[str, Any]:
    nouls = {
        "engage": 0.9,
        "consult_K": 0.8,
        "consult_W": 0.1,
        "consult_P": 0.9,
        "consult_M": 0.9,
        "ambiguous": 0.05,
    }
    answers: dict[str, Any] = {q: {"noul": v} for q, v in nouls.items()}
    answers["coverage"] = {"choice": "ghost", "confidence": 0.7}
    return answers | over


class Replies(FakeHttp):
    """jev replies in order: an answers dict, or an exception to raise."""

    def __init__(self, *replies: dict[str, Any] | Exception) -> None:
        super().__init__()
        self.replies = list(replies)

    def post_json(
        self, url: str, body: Mapping[str, Any], headers: Mapping[str, str], timeout: float
    ) -> dict[str, Any]:
        self.calls.append((url, dict(body), timeout))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return {"model": body["model"], "answers": reply, "usage": {}}


def test_jev_transport_and_its_fallbacks() -> None:
    from lectern.http import HttpStatusError

    env = {"OPENROUTER_API_KEY": "or-key", "LECTERN_JEV_MODEL": "x/jev"}
    http = Replies(jev_answers())
    got = triage("What changed today?", PROBES, SPEC, env, http)
    assert got.by == "jev" and got.kind == "ghost" and got.coverage["ghost"] == 0.7
    assert got.route["W"] is not None and got.route["K"] is None and got.ambiguity == 0.05
    url, body, timeout = http.calls[0]
    assert url == JEV_URL and body["model"] == "x/jev" and timeout == 8.0
    questions = body["questions"]
    assert questions["engage"]["type"] == "noul" and set(questions["engage"]["criteria"]) == {"true", "false"}
    assert questions["coverage"]["type"] == "choice"
    assert set(questions["coverage"]["criteria"]) == {"covered", "rare", "ghost"}
    retried = Replies(HttpStatusError(429, JEV_URL), jev_answers())
    assert triage("q", PROBES, SPEC, env, retried).by == "jev" and len(retried.calls) == 2
    twice = triage(
        "q", PROBES, SPEC, env, Replies(HttpStatusError(529, JEV_URL), HttpStatusError(529, JEV_URL))
    )
    assert twice.by == "rules" and "HTTP 529" in twice.note
    denied = Replies(HttpStatusError(401, JEV_URL))
    assert (
        triage("q", PROBES, SPEC, env, denied).note == "jev failed (HTTP 401); used rules"
        and len(denied.calls) == 1
    )
    bug = triage("q", PROBES, SPEC, env, Replies(HttpStatusError(422, JEV_URL)))
    assert bug.by == "rules" and "request bug" in bug.note
    timed_out = triage("q", PROBES, SPEC, env, Replies(TimeoutError("8 s")))
    assert timed_out.by == "rules" and "jev failed (TimeoutError)" in timed_out.note
    for bad in ({"engage": {"noul": 1.4}}, {"engage": {"noul": True}}, {"coverage": {"choice": "maybe"}}):
        assert "JevUnusable" in triage("q", PROBES, SPEC, env, Replies(jev_answers(**bad))).note
    assert triage("q", PROBES, SPEC, {}, http).by == "rules"  # no key: rules, no call
    rules_only = SPEC.model_copy(update={"triage": SPEC.triage.model_copy(update={"provider": "rules"})})
    assert triage("q", PROBES, rules_only, env, http).by == "rules" and len(http.calls) == 1
    assert len(str(jev_state("x" * 5000, PROBES)).encode()) <= MAX_STATE_BYTES


def test_rules_triage_classes() -> None:
    covered = rules(Probes(6.0, 0, False, 3, ("deck_search", "memory_search"), "real", False))
    assert covered.kind == "covered" and covered.route["M"] == "no similar past question"
    assert covered.route["P"] == "K holds the answer; the model is not needed" and covered.hops == 0
    ghost = rules(Probes(0.0, 0, False, 3, ("deck_search",), "real", False))
    assert ghost.kind == "ghost" and ghost.route["P"] is None and ghost.route["W"] == "tool not enabled"


def src(source: str, answer: str, r: float, g: float) -> SourceReport:
    return SourceReport(source=source, status="done", answer=answer, r=r, g=g)  # type: ignore[arg-type]


def test_bayesian_and_dempster_shafer_against_hand_computed_cases() -> None:
    f = fuse([src("K", "Answer A. [slide:1:body]", 0.9, 0.2), src("W", "answer b", 0.6, 0.3)])
    assert f.candidates == ["answer a", "answer b", NONE]  # half their words differ: two candidates
    u = 1 / 3
    raw_a = u * (0.8 * (0.9 + 0.1 * u) + 0.2 * u) * (0.7 * (0.4 * u) + 0.3 * u)
    raw_b = u * (0.8 * (0.1 * u) + 0.2 * u) * (0.7 * (0.6 + 0.4 * u) + 0.3 * u)
    raw_none = u * (0.8 * (0.1 * u) + 0.2 * u) * (0.7 * (0.4 * u) + 0.3 * u)
    z = raw_a + raw_b + raw_none
    assert f.z == pytest.approx(z) and f.bayes["answer a"] == pytest.approx(raw_a / z)
    assert f.bayes[NONE] == pytest.approx(raw_none / z)
    # DS: conflict 0.9·0.6; {a} 0.9·0.4, {b} 0.1·0.6, Θ 0.1·0.4, all over 1 - 0.54.
    assert f.kappa == pytest.approx(0.54)
    assert f.ds["answer a"] == pytest.approx(0.36 / 0.46) and f.ds["answer b"] == pytest.approx(0.06 / 0.46)
    assert f.ds["Θ"] == pytest.approx(0.04 / 0.46)
    agree = fuse([src("K", "same", 0.9, 0.1), src("M", "Same!", 0.6, 0.5)])
    assert agree.kappa == 0 and agree.ds["same"] == pytest.approx(1 - 0.1 * 0.4)
    assert fuse([]).best == NONE and normalise("[slide:2:body]") == NONE
    paraphrase = fuse(
        [
            src("K", "The ferry route doubled harbour visitors.", 0.9, 0.2),
            src("M", "Harbour visitors doubled: the ferry route. [mem:x]", 0.6, 0.5),
        ]
    )
    assert paraphrase.kappa == 0 and len(paraphrase.candidates) == 2


def test_decide() -> None:
    rules_ = Decision()
    one = fuse([src("K", "yes", 0.9, 0.1)])
    assert decide(one, rules_, 0.1).verdict == "answer"
    assert decide(one, rules_, 0.9).verdict == "ask"
    assert decide(one, Decision(ask_when="never"), 0.9).verdict == "answer"
    weak = fuse([src("K", "yes", 0.3, 0.6)])
    assert decide(weak, rules_, 0.1).verdict == "qualify"
    assert decide(fuse([src("K", "", 0.9, 0.95)]), rules_, 0.1).verdict == "abstain"
    low = fuse([src("K", "a", 0.2, 0.2), src("W", "b", 0.2, 0.2), src("P", "c", 0.2, 0.2)])
    assert decide(low, Decision(qualify_band=0.0), 0.1).verdict == "abstain"
    assert agreement("ferry route doubled visitors", [WEB_TEXT, "unrelated"]) == 0.5
    assert agreement("", [WEB_TEXT]) == 0.0


def test_feedback_moves_memory_reliability_and_jobs_export() -> None:
    import json

    from conftest import REPO
    from fastapi.testclient import TestClient

    from lectern.api import create_app

    with TestClient(create_app(Store(), FakeProvider())) as client:
        pptx = (REPO / "decks" / "kettle-quarterly-review.pptx").read_bytes()
        d = client.post("/decks", files={"file": ("k.pptx", pptx)}).json()["id"]
        ask = {"question": "Why did the harbour cafe grow?"}
        first = client.post(f"/decks/{d}/slides/2/ask?wait=true", json=ask).json()
        assert client.post(f"/jobs/{first['id']}/feedback", json={"vote": "up"}).json()["feedback"] == 1
        assert client.post(f"/jobs/{first['id']}/feedback", json={"vote": "meh"}).status_code == 422
        second = client.post(f"/decks/{d}/slides/2/ask?wait=true", json=ask).json()
        m = next(s for s in second["sources"] if s["source"] == "M")
        assert m["status"] == "done" and m["r"] == pytest.approx(0.3 + 0.6 * 2 / 3, abs=1e-3)
        lines = [json.loads(x) for x in client.get("/jobs.jsonl").text.splitlines()]
        assert [x["id"] for x in lines] == [first["id"], second["id"]]
        assert lines[0]["feedback"] == 1 and lines[0]["verdict"] == "answer"
        assert lines[1]["triage"]["probes"]["m_hits"] == 1
