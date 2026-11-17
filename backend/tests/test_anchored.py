"""Questions about the slide or deck they are asked on (v0.4.1): System1 sees where the question
was asked, and may lower confidence on them but never abstain, ask back or cut the deck."""

from __future__ import annotations

import json

import pytest
from test_confidence import FakeHttp, run_job

from lectern.agents import resolve
from lectern.jobs.triage import MAX_STATE_BYTES, Probes, jev_state
from lectern.models import Deck
from lectern.store import Store

# What jev answered on prod for these questions, before it knew where they were asked.
DOUBTFUL = {
    "engage": {"noul": 0.33},
    "consult_K": {"noul": 0.2},
    "consult_W": {"noul": 0.5},
    "consult_P": {"noul": 0.5},
    "consult_M": {"noul": 0.5},
    "coverage": {"choice": "ghost", "confidence": 0.56},
    "ambiguous": {"noul": 0.86},
}


@pytest.mark.parametrize(
    ("question", "n"), [("what is this talk about?", 1), ("what are the core ideas of the slide?", 3)]
)
def test_questions_about_the_deck_answer_from_it_despite_a_doubtful_system1(
    store: Store, kettle: Deck, monkeypatch: pytest.MonkeyPatch, question: str, n: int
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-sentinel-not-a-key")
    monkeypatch.delenv("SYSTEM1_MODEL_PROVIDER", raising=False)
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    http = FakeHttp(jev=DOUBTFUL)
    job = run_job(store, kettle, question, http, n=n)
    conf = job.answer.confidence or {}  # type: ignore[union-attr]
    assert conf["triage"]["by"] == "jev" and conf["triage"]["engage"] >= 0.9
    assert job.status == "answered", job.answer
    sent = http.calls[0][1]["state"]
    assert sent["asked_on"]["deck"] == kettle.title and sent["asked_on"]["slide"] == n
    assert "this deck" in sent["context"]
    k = next(s for s in job.sources if s.source == "K")
    assert k.status != "skipped"


def test_the_state_fits_by_cutting_the_outline_first() -> None:
    probes = Probes(0.0, 0, False, 2, ("deck_search",), "fake", False, True)
    outline = "\n".join(f"{i}. A slide title that goes on for a while" for i in range(200))
    about = {"deck": "Talk", "slides": 200, "slide": 1, "slide_title": "Intro", "outline": outline}
    state = jev_state("what is this talk about?", probes, about)
    assert len(json.dumps(state).encode()) <= MAX_STATE_BYTES
    assert state["question"] == "what is this talk about?" and state["asked_on"]["outline"].startswith("0.")


def test_a_web_key_enables_the_web_researcher(store: Store, kettle: Deck) -> None:
    assert "web_search" not in resolve(kettle, 1, env={}).spec.tools
    tools = resolve(kettle, 1, env={"EXA_API_KEY": "x"}).spec.tools
    assert "web_search" in tools and "fetch_url" in tools


def test_past_answers_never_outweigh_the_deck(store: Store, kettle: Deck) -> None:
    from lectern.graph.nodes.answer import SOURCES_FIRST, system_prompt
    from lectern.graph.nodes.assemble import assemble
    from lectern.graph.state import Block, GraphState, Ports
    from lectern.jobs.fusion import fuse
    from lectern.models import SourceReport

    deck_says = SourceReport(source="K", status="done", answer="A new ferry route", r=0.9, g=0.05)
    memory_says = SourceReport(source="M", status="done", answer="The context does not say", r=0.5, g=0.5)
    fusion = fuse([deck_says, memory_says], p_none=0.05)
    assert fusion.kappa == 0.0 and max(fusion.bayes, key=lambda y: fusion.bayes[y]) == fusion.votes["K"]
    stale = Block("mem:old", "Why did it grow?\nThe context does not say.")
    found = Block("slide:2:notes", "A new ferry route doubled visitors.")
    state = GraphState(
        template="answer", deck=kettle, deck_id=kettle.id, slide=2, question="Why?", evidence=(stale, found)
    )
    blocks = assemble(state, Ports(store=store)).delta["blocks"]
    assert [b.id for b in blocks][-1] == "mem:old"  # conversation goes after every source
    assert SOURCES_FIRST in system_prompt(GraphState(template="answer", blocks=blocks))
