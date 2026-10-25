"""The writer ⇄ fact-checker → localizer hand-off, built as a Microsoft Agent Framework workflow.

::

    writer ──Draft──▶ fact-checker ──Approved──▶ localizer ──▶ output
       ▲                   │
       └──DraftRequest─────┘   (rejected: reasons go back to the writer, once)

Each executor wraps one crew agent. Any executor can end the run early with an ``Outcome`` whose text is
``None`` (model unavailable, rejected twice, translation refused); the crew then airs the template.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Never

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, WorkflowViz, handler

from booth.agents.base import Job, Timer
from booth.agents.fact_checker import FactChecker
from booth.agents.localizer import Localizer
from booth.agents.stats_producer import moment_context
from booth.agents.writers import Writers
from booth.facts import FactSheet
from booth.llm import LLMUnavailable
from booth.profile import ViewerProfile

MAX_ATTEMPTS = 2
WRITER_NAMES = {"pbp": "play-by-play", "color": "analyst", "recap": "recap-editor"}


@dataclass
class DraftContext:
    """Everything the executors share for one segment."""

    kind: str
    job: Job
    profile: ViewerProfile
    sheet: FactSheet
    trace: object
    notes: list[str] = field(default_factory=list)


@dataclass
class DraftRequest:
    attempt: int
    feedback: list[str] = field(default_factory=list)


@dataclass
class Draft:
    text: str
    attempt: int


@dataclass
class Approved:
    text: str


@dataclass
class Outcome:
    text: str | None
    reason: str


class WriterExecutor(Executor):
    def __init__(self, writers: Writers, context: DraftContext):
        super().__init__(id="writer")
        self.writers = writers
        self.context = context

    @handler
    async def write(self, request: DraftRequest, ctx: WorkflowContext[Draft, Outcome]) -> None:
        c = self.context
        name = WRITER_NAMES[c.kind]
        timer = Timer()
        c.trace(name, "start", f"drafting (attempt {request.attempt})", 0)
        try:
            text = await self.writers.write_model(c.kind, c.job, c.profile, c.sheet, request.feedback or None)
        except LLMUnavailable as exc:
            c.trace(name, "fallback", str(exc), timer.ms)
            c.notes.append(str(exc))
            await ctx.yield_output(Outcome(None, str(exc)))
            return
        c.trace(name, "done", text[:90], timer.ms)
        await ctx.send_message(Draft(text, request.attempt))


class FactCheckExecutor(Executor):
    def __init__(self, checker: FactChecker, context: DraftContext):
        super().__init__(id="fact-checker")
        self.checker = checker
        self.context = context

    @handler
    async def check(self, draft: Draft, ctx: WorkflowContext[DraftRequest | Approved, Outcome]) -> None:
        c = self.context
        timer = Timer()
        verdict = self.checker.check(draft.text, c.kind, c.job.event, c.job.state, c.sheet)
        if verdict.approved and c.kind in ("color", "recap"):
            verdict = await self.checker.review(
                draft.text,
                {
                    "moment": moment_context(c.job),
                    "facts": c.sheet.to_list(),
                    "score": c.job.state.snapshot["score"],
                },
            )
        detail = "; ".join(verdict.reasons) or (
            "numbers and names traced to data"
            + (" + model claim review" if verdict.reviewed_by_model else "")
        )
        c.trace("fact-checker", "approved" if verdict.approved else "rejected", detail, timer.ms)
        if verdict.approved:
            await ctx.send_message(Approved(draft.text), target_id="localizer")
        elif draft.attempt < MAX_ATTEMPTS:
            c.notes.append(f"draft {draft.attempt} rejected: {detail}")
            await ctx.send_message(DraftRequest(draft.attempt + 1, verdict.reasons), target_id="writer")
        else:
            c.notes.append(f"draft {draft.attempt} rejected: {detail}")
            await ctx.yield_output(Outcome(None, "rejected twice"))


class LocalizerExecutor(Executor):
    def __init__(self, localizer: Localizer, context: DraftContext):
        super().__init__(id="localizer")
        self.localizer = localizer
        self.context = context

    @handler
    async def localize(self, approved: Approved, ctx: WorkflowContext[Never, Outcome]) -> None:
        c = self.context
        if c.profile.lang == "en":
            await ctx.yield_output(Outcome(approved.text, "approved"))
            return
        timer = Timer()
        try:
            text = await self.localizer.translate(approved.text, c.profile.lang)
        except LLMUnavailable as exc:
            c.trace("localizer", "fallback", str(exc), timer.ms)
            c.notes.append(f"translation failed: {exc}")
            await ctx.yield_output(Outcome(None, "translation refused"))
            return
        c.trace("localizer", "done", f"adapted for {c.profile.language_name}", timer.ms)
        await ctx.yield_output(Outcome(text, "approved"))


def build_draft_workflow(writers: Writers, checker: FactChecker, localizer: Localizer, context: DraftContext):
    writer = WriterExecutor(writers, context)
    fact_checker = FactCheckExecutor(checker, context)
    local = LocalizerExecutor(localizer, context)
    return (
        WorkflowBuilder(
            start_executor=writer,
            name="booth-draft",
            description="Writer drafts, fact-checker approves or sends it back, localizer adapts it.",
            max_iterations=10,
            output_from=[writer, fact_checker, local],
        )
        .add_edge(writer, fact_checker)
        .add_edge(fact_checker, writer)
        .add_edge(fact_checker, local)
        .build()
    )


async def run_draft(
    writers: Writers, checker: FactChecker, localizer: Localizer, context: DraftContext
) -> Outcome:
    workflow = build_draft_workflow(writers, checker, localizer, context)
    result = await workflow.run(DraftRequest(1))
    outputs = [o for o in result.get_outputs() if isinstance(o, Outcome)]
    return outputs[-1] if outputs else Outcome(None, "workflow produced no output")


def mermaid() -> str:
    """The draft workflow as a Mermaid diagram (for the docs)."""
    context = DraftContext("pbp", None, ViewerProfile(), FactSheet(), lambda *a: None)  # type: ignore[arg-type]
    workflow = build_draft_workflow(Writers(None), FactChecker(), Localizer(None), context)
    return WorkflowViz(workflow).to_mermaid()
