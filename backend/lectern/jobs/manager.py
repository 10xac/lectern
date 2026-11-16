"""Run jobs in the background: ``triage → research (fan-out) → fuse → answer graph``.

A job is an ``asyncio`` task in the API process; there is no external queue. Researchers run in
parallel (``asyncio.gather`` over worker threads, at most ``budget.max_researchers`` at a time).
The answer is the existing ``answer`` graph (gate → route → assemble → answer → cite → persist)
with the researchers' evidence in its context, posted to the thread of the slide that was asked,
whichever slide anyone has open.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import time
from collections.abc import AsyncIterator, Callable, Sequence

from lectern import service
from lectern.agents import AgentConfig, deck_agent, slide_agent
from lectern.agents.spec import Budget, RequestAgent
from lectern.dna import DNA
from lectern.files import FileError
from lectern.graph.state import Block
from lectern.http import Http, HttpxPort
from lectern.jobs import research, steps  # web registers the W researcher
from lectern.jobs.fusion import Fusion, Outcome, decide, fuse
from lectern.jobs.research import Context, Found, OutOfCalls, ToolCalls, skipped
from lectern.jobs.rows import JobRows
from lectern.jobs.steps import probes_for
from lectern.jobs.triage import Triage, triage
from lectern.models import TERMINAL, Answer, Deck, Job, JobEvent, JobStatus, SourceName, SourceReport, Turn
from lectern.providers.base import Provider
from lectern.store import Store

HISTORY_TURNS = 6


class DailyBudget:
    """At most ``limit`` asks per UTC day across every surface (asks spend paid API keys)."""

    def __init__(self, limit: int) -> None:
        self.limit, self.day, self.used = limit, "", 0

    def take(self) -> None:
        today = time.strftime("%Y-%m-%d", time.gmtime())
        if today != self.day:
            self.day, self.used = today, 0
        if self.used >= self.limit:
            raise FileError(429, f"the daily budget of {self.limit} questions is spent; try again tomorrow")
        self.used += 1


class JobManager:
    """Starts, tracks, streams and cancels jobs. One per API process."""

    def __init__(
        self,
        store: Store,
        provider: Provider,
        providers: service.ProviderFactory | None = None,
        clock: Callable[[], float] = time.perf_counter,
        http: Http | None = None,
        dna: DNA | None = None,
    ) -> None:
        self.dna = dna
        self.budget = DailyBudget(int(os.environ.get("LECTERN_MAX_ASKS_PER_DAY", "200")))
        self.store, self.provider, self.providers, self.clock = store, provider, providers, clock
        self.http: Http = http or HttpxPort()
        self.rows = JobRows(store)
        self.tasks: dict[str, asyncio.Task[None]] = {}
        self.changed: dict[str, asyncio.Event] = {}

    def recover(self) -> int:
        """Mark jobs a previous process left running as ``failed: interrupted``."""
        return self.rows.mark_interrupted()

    def submit(self, deck: Deck, n: int | None, question: str, override: RequestAgent | None = None) -> Job:
        """Queue a question on slide ``n`` (``None``: the deck) and start it. Needs a running loop.

        The agent is resolved now, so a refused override raises ``SpecError`` before any job exists.
        """
        agent = slide_agent(deck, n, override) if n is not None else deck_agent(deck, override)
        assert deck.id is not None
        self.budget.take()
        history = [Turn(role=m.role, text=m.text) for m in self.rows.messages(deck.id, n)][-HISTORY_TURNS:]
        job = self.rows.create(deck.id, n, question)
        self.rows.add_message(deck.id, n, "user", question, job.id)
        self.emit(job.id, "status", {"status": "queued"})
        task = asyncio.get_running_loop().create_task(self.run(job, deck, agent, history, override))
        self.tasks[job.id] = task
        return job

    async def wait(self, job_id: str) -> Job | None:
        """Wait for a job's task to end (tests and ``?wait=true``), then return the job."""
        task = self.tasks.get(job_id)
        if task is not None:
            await asyncio.wait({task})
        return self.rows.get(job_id)

    def cancel(self, job_id: str) -> bool:
        task = self.tasks.get(job_id)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    # progress ------------------------------------------------------------------------------

    def emit(self, job_id: str, kind: str, data: dict[str, object]) -> JobEvent:
        event = self.rows.add_event(job_id, kind, data | {"t": round(self.clock(), 6)})
        self.changed.setdefault(job_id, asyncio.Event()).set()
        return event

    def status(self, job_id: str, status: JobStatus) -> None:
        self.rows.set_status(job_id, status)
        self.emit(job_id, "status", {"status": status})

    async def stream(self, job_id: str, after: int = 0, idle_s: float = 1.0) -> AsyncIterator[JobEvent]:
        """Every event after ``after``, then new ones as they happen, until the job has ended."""
        while True:
            signal = self.changed.setdefault(job_id, asyncio.Event())
            signal.clear()
            events = self.rows.events(job_id, after)
            for event in events:
                after = event.seq
                yield event
            job = self.rows.get(job_id)
            if job is None or (job.status in TERMINAL and not events):
                return
            if not events:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(signal.wait(), idle_s)

    # the pipeline --------------------------------------------------------------------------

    async def run(
        self, job: Job, deck: Deck, agent: AgentConfig, history: Sequence[Turn], override: RequestAgent | None
    ) -> None:
        sources: list[SourceReport] = []
        try:
            status, answer, notes = await self.pipeline(job, deck, agent, history, override, sources)
        except asyncio.CancelledError:
            self.end(job, "cancelled", None, sources, ["cancelled"])
            return
        except Exception as exc:  # the job fails, the process does not
            self.rows.set_status(job.id, "failed", error=f"{type(exc).__name__}: {exc}")
            self.emit(job.id, "done", {"status": "failed"})
            return
        finally:
            self.tasks.pop(job.id, None)
        self.rows.add_message(job.deck_id, job.slide, "agent", answer.answer, job.id, answer)
        self.end(job, status, answer, sources, notes)

    def end(
        self,
        job: Job,
        status: JobStatus,
        answer: Answer | None,
        sources: list[SourceReport],
        notes: list[str],
    ) -> None:
        self.rows.finish(job.id, status, answer, sources, notes)
        self.emit(job.id, "done", {"status": status})

    async def pipeline(
        self,
        job: Job,
        deck: Deck,
        agent: AgentConfig,
        history: Sequence[Turn],
        override: RequestAgent | None,
        sources: list[SourceReport],
    ) -> tuple[JobStatus, Answer, list[str]]:
        """triage → research → fuse → decide → (answer graph | ask | abstain)."""
        spec, env = agent.spec, dict(os.environ)
        provider = self.providers(spec.model) if self.providers else self.provider
        ctx = Context(deck, job.slide, job.question, provider, self.rows, self.http, env, self.dna)
        self.status(job.id, "triaging")
        tri = await asyncio.to_thread(triage, job.question, probes_for(ctx, spec, env), spec, env, self.http)
        self.emit(job.id, "triage", tri.public())
        sources.extend(skipped(s, why) for s, why in tri.route.items() if why is not None)
        if tri.engage < 0.5:
            outcome = Outcome("abstain", "the question is out of scope or ill-posed")
            return (
                "abstained",
                self.said(agent, steps.abstain_text(tri, sources, outcome.why), tri, None, outcome, sources),
                [],
            )
        self.status(job.id, "researching")
        found, notes = await self.research(job.id, ctx, tri.consult, spec.budget)
        sources.extend(rep for rep, _ in found)
        self.status(job.id, "fusing")
        fusion = fuse(sources, p_none=tri.coverage.get("ghost"))
        outcome = decide(fusion, spec.behaviour.decision, tri.ambiguity)
        self.emit(job.id, "fuse", fusion.public() | {"verdict": outcome.verdict, "why": outcome.why})
        conf = steps.confidence(tri, fusion, outcome, sources)
        if outcome.verdict == "ask":
            return (
                "asked",
                self.said(agent, steps.ask_text(job.question), tri, fusion, outcome, sources),
                notes,
            )
        if outcome.verdict == "abstain":
            text = steps.abstain_text(tri, sources, outcome.why)
            return "abstained", self.said(agent, text, tri, fusion, outcome, sources), notes
        evidence = [b for _, blocks in found for b in blocks]
        answer = await asyncio.to_thread(self.answer, deck, job, history, override, evidence)
        if outcome.verdict == "qualify":
            answer = steps.qualified(answer, outcome.why)
        return "answered", answer.model_copy(update={"confidence": conf}), notes

    @staticmethod
    def said(
        agent: AgentConfig,
        text: str,
        tri: Triage,
        fusion: Fusion | None,
        outcome: Outcome,
        sources: Sequence[SourceReport],
    ) -> Answer:
        """An answer the job wrote itself (ask or abstain): no graph run, no citations."""
        conf = steps.confidence(tri, fusion, outcome, sources)
        return Answer(answer=text, agent=agent.name, outcome=outcome.verdict, confidence=conf)

    async def research(
        self, job_id: str, ctx: Context, consult: Sequence[SourceName], budget: Budget
    ) -> tuple[list[Found], list[str]]:
        """Run one researcher per source in parallel, within the job's time and tool-call budget."""
        gate, calls = asyncio.Semaphore(budget.max_researchers), ToolCalls(budget.max_tool_calls)
        found: list[Found] = []
        notes: list[str] = []

        async def one(source: SourceName) -> None:
            async with gate:
                self.emit(job_id, "researcher", {"source": source, "state": "running"})
                try:
                    rep, blocks = await asyncio.to_thread(research.RESEARCHERS[source], ctx, calls)
                except OutOfCalls:
                    rep, blocks = skipped(source, "tool-call budget spent"), []
                    notes.append("ran out of tool calls")
                except Exception as exc:  # one source failing does not fail the job
                    rep = SourceReport(source=source, status="failed", reason=type(exc).__name__)
                    blocks = []
                found.append((rep, blocks))
                self.emit(
                    job_id, "researcher", {"source": source, "state": rep.status, "blocks": len(blocks)}
                )

        try:
            async with asyncio.timeout(budget.max_seconds):
                await asyncio.gather(*(one(s) for s in consult))
        except TimeoutError:
            notes.append(f"ran out of time after {budget.max_seconds:g} s; answering from what was found")
            self.emit(job_id, "budget", {"reason": "time"})
            done = {rep.source for rep, _ in found}
            found += [
                (SourceReport(source=s, status="timeout", reason="out of time"), [])
                for s in consult
                if s not in done
            ]
        return found, notes

    def answer(
        self,
        deck: Deck,
        job: Job,
        history: Sequence[Turn],
        override: RequestAgent | None,
        evidence: list[Block],
    ) -> Answer:
        return service.ask(
            self.store,
            self.provider,
            deck,
            job.slide,
            job.question,
            history,
            clock=self.clock,
            override=override,
            providers=self.providers,
            evidence=evidence,
        )
