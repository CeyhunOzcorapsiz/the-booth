"""The crew turns a director's job into on-air segments.

Hand-offs for a model-backed segment::

    stats producer (tool calls) -> writer -> fact-checker --rejected--> writer (with feedback, once)
                                                   |approved
                                                   v
                                              localizer -> on air

Any failure along the way (timeout, quota, rejected twice, translation changed a number) falls back to the
deterministic template for that segment, and the trace says so. A broadcast never stalls on a model.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import replace

from booth.agents import templates
from booth.agents.base import SPEAKERS, Job, Segment, Timer
from booth.agents.fact_checker import FactChecker
from booth.agents.localizer import Localizer
from booth.agents.stats_producer import StatsProducer
from booth.agents.writers import Writers
from booth.facts import FactSheet, StatsDesk
from booth.llm import LLMRuntime, LLMUnavailable
from booth.profile import ViewerProfile
from booth.telemetry import tracer
from booth.workflow import DraftContext, run_draft

Trace = Callable[[str, str, str, int], None]
WRITER_NAMES = {
    "pbp": "play-by-play",
    "color": "analyst",
    "recap": "recap-editor",
    "stats": "stats-producer",
    "explain": "guide",
    "spatial": "guide",
}
CACHE_SIZE = 4000


class _LRU(OrderedDict):
    def get_item(self, key):
        if key in self:
            self.move_to_end(key)
            return self[key]
        return None

    def put(self, key, value) -> None:
        self[key] = value
        self.move_to_end(key)
        while len(self) > CACHE_SIZE:
            self.popitem(last=False)


class Crew:
    def __init__(self, runtime: LLMRuntime | None = None):
        self.runtime = runtime
        self.stats = StatsProducer(runtime)
        self.writers = Writers(runtime)
        self.checker = FactChecker(runtime)
        self.localizer = Localizer(runtime)
        self._segments = _LRU()  # (seed, event, kind, profile) -> Segment, shared by every viewer

    def use_model(self, job: Job) -> bool:
        return (
            self.runtime is not None
            and self.runtime.available()
            and job.importance >= self.runtime.config.min_importance
        )

    async def produce(self, job: Job, profile: ViewerProfile, trace: Trace) -> list[Segment]:
        """Run the hand-offs for one job. Each hand-off is also recorded on a ``booth.job`` span."""
        attributes = {
            "booth.job": job.id,
            "booth.event": job.event.id,
            "booth.event_type": job.event.type,
            "booth.kinds": ",".join(job.kinds),
            "booth.profile": profile.key(),
        }
        with tracer.start_as_current_span("booth.job", attributes=attributes) as span:

            def traced(agent: str, status: str, detail: str, ms: int) -> None:
                span.add_event(f"{agent}.{status}", {"detail": detail[:200], "ms": ms})
                trace(agent, status, detail, ms)

            return await self._produce(job, profile, traced)

    async def _produce(self, job: Job, profile: ViewerProfile, trace: Trace) -> list[Segment]:
        cached = [self._segments.get_item(self._key(job, kind, profile)) for kind in job.kinds]
        if all(cached):
            trace("crew", "cache", f"{len(cached)} segment(s) reused from another viewer", 0)
            return [replace(seg, job=job.id) for seg in cached]

        new_stories = [
            st for st in job.state.snapshot.get("storylines", []) if st["event_id"] == job.event.id
        ]
        for story in new_stories:
            trace("storyline", "done", f"{story['kind'].replace('_', ' ')}: {story['en']}", 0)

        sheet, caption = FactSheet(), None
        if any(kind in ("color", "stats", "recap") for kind in job.kinds):
            timer = Timer()
            trace("stats-producer", "start", "pulling context with tools", 0)
            sheet, caption, source = await self.stats.collect(job, self.use_model(job))
            if new_stories:
                StatsDesk(
                    job.state, sheet
                ).storylines()  # writers always get the narrative behind this moment
            via = "model tool calls" if source == "ai" else "rule-based selection"
            trace("stats-producer", "done", f"{len(sheet)} facts via {via}", timer.ms)

        segments = []
        for kind in job.kinds:
            segment = await self._segment(kind, job, profile, sheet, caption, trace)
            if segment and segment.text:
                self._segments.put(self._key(job, kind, profile), segment)
                segments.append(segment)
        return segments

    @staticmethod
    def _key(job: Job, kind: str, profile: ViewerProfile) -> tuple:
        return job.state.match.seed, job.event.id, kind, profile.key()

    async def _segment(
        self, kind: str, job: Job, profile: ViewerProfile, sheet: FactSheet, caption: str | None, trace: Trace
    ) -> Segment | None:
        notes: list[str] = []
        text, source, lang = None, "template", profile.lang

        if kind in ("pbp", "color", "recap") and self.use_model(job):
            # writer ⇄ fact-checker → localizer, as a Microsoft Agent Framework workflow
            context = DraftContext(kind, job, profile, sheet, trace, notes)
            outcome = await run_draft(self.writers, self.checker, self.localizer, context)
            text, source = (outcome.text, "ai") if outcome.text else (None, "template")
        elif kind == "stats" and caption:
            verdict = self.checker.check(caption, kind, job.event, job.state, sheet)
            trace(
                "fact-checker",
                "approved" if verdict.approved else "rejected",
                "; ".join(verdict.reasons) or "caption numbers match tool results",
                0,
            )
            text, source = (caption, "ai") if verdict.approved else (None, "template")
            if text is not None and profile.lang != "en":
                timer = Timer()
                try:
                    text = await self.localizer.translate(text, profile.lang)
                    trace("localizer", "done", f"adapted for {profile.language_name}", timer.ms)
                except LLMUnavailable as exc:
                    trace("localizer", "fallback", str(exc), timer.ms)
                    notes.append(f"translation failed: {exc}")
                    text, source = None, "template"

        if text is None:
            text, lang = await self._template(kind, job, profile, sheet, trace, notes)

        evidence = sheet.to_list() if kind in ("color", "stats", "recap") else [self._event_evidence(job)]
        return Segment(
            job=job.id,
            kind=kind,
            speaker=SPEAKERS[kind],
            text=text,
            lang=lang,
            source=source,
            verified=True,
            event_id=job.event.id,
            minute=job.event.display_minute,
            importance=job.importance,
            evidence=evidence,
            notes=notes,
        )

    async def _template(
        self, kind: str, job: Job, profile: ViewerProfile, sheet: FactSheet, trace: Trace, notes: list[str]
    ) -> tuple[str, str]:
        if kind in ("color", "recap", "stats"):
            StatsProducer.default_selection(StatsDesk(job.state, sheet), job)
        native = profile.lang in templates.SUPPORTED
        lang = profile.lang if native else "en"
        text = Writers.write_template(kind, job, profile, sheet, lang)
        if not native and self.runtime is not None and self.runtime.available() and text:
            try:
                text = await self.localizer.translate(text, profile.lang)
                lang = profile.lang
                trace("localizer", "done", f"template adapted for {profile.language_name}", 0)
            except LLMUnavailable:
                notes.append(f"{profile.language_name} unavailable offline; English shown")
        elif not native:
            notes.append(f"{profile.language_name} needs a model; English shown")
        trace(WRITER_NAMES[kind], "template", text[:90], 0)
        verdict = self.checker.check(text, kind, job.event, job.state, sheet)
        if not verdict.approved:
            notes.append("template check: " + "; ".join(verdict.reasons))
        trace(
            "fact-checker",
            "approved" if verdict.approved else "rejected",
            "; ".join(verdict.reasons) or "template numbers and names traced to data",
            0,
        )
        return text, lang

    @staticmethod
    def _event_evidence(job: Job) -> dict:
        event = job.event
        player = job.state.match.player(event.player)
        who = f" · {player.name}" if player else ""
        return {
            "id": event.id,
            "label": "Event",
            "value": f"{event.display_minute} {event.type.replace('_', ' ')}{who}",
        }
