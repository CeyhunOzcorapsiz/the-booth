"""Runs one viewer's broadcast: replays the match clock, updates shared state, and drives the crew.

Two cooperating tasks share a queue:

* the **feed** replays events at ``speed`` match-seconds per real second, applies them to ``MatchState`` and
  asks the director what to cover;
* the **producer** hands each job to the crew. If the crew falls behind live play, routine jobs are dropped
  (a real gallery would rather skip a throw-in than describe it a minute late); big moments never are.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from booth.agents.director import Director
from booth.crew import Crew
from booth.profile import ViewerProfile
from booth.sim.match import Match
from booth.state import MatchState

log = logging.getLogger("booth.orchestrator")
STALE_AFTER_S = 30.0
MUST_AIR = 0.8


class Broadcast:
    def __init__(
        self,
        match: Match,
        profile: ViewerProfile,
        crew: Crew,
        *,
        speed: float = 20.0,
        start_minute: float = 0.0,
        max_gap_s: float = 2.5,
        drop_stale: bool = True,
    ):
        if speed <= 0:
            raise ValueError("speed must be positive")
        self.match = match
        self.profile = profile
        self.crew = crew
        self.speed = speed
        self.start_clock = max(0.0, start_minute) * 60
        self.max_gap_s = max_gap_s
        self.drop_stale = drop_stale
        self.state = MatchState(match)

    async def stream(self) -> AsyncIterator[dict]:
        out: asyncio.Queue[dict] = asyncio.Queue()
        jobs: asyncio.Queue = asyncio.Queue()
        director = Director(self.profile)

        def trace(job_id: str, agent: str, status: str, detail: str, ms: int) -> None:
            out.put_nowait(
                {"type": "trace", "job": job_id, "agent": agent, "status": status, "detail": detail, "ms": ms}
            )

        async def feed() -> None:
            previous = None
            for event in self.match.events:
                live = event.clock >= self.start_clock
                if live and previous is not None and previous.clock >= self.start_clock:
                    gap = event.clock - previous.clock if event.period == previous.period else 3.0
                    await asyncio.sleep(min(max(gap, 0.0) / self.speed, self.max_gap_s))
                self.state.apply(event)
                previous = event
                if not live:
                    continue
                await out.put({"type": "event", "event": event.to_dict(), "state": self.state.snapshot()})
                job = director.plan(event, self.state)
                if job:
                    trace(
                        job.id,
                        "director",
                        "planned",
                        f"{event.type.replace('_', ' ')} → {', '.join(job.kinds)} (importance {job.importance})",
                        0,
                    )
                    await jobs.put(job)
            await jobs.put(None)

        async def produce() -> None:
            while (job := await jobs.get()) is not None:
                now = self.state.last_event
                lag = now.clock - job.event.clock if now and now.period == job.event.period else 0.0
                if self.drop_stale and job.importance < MUST_AIR and lag > STALE_AFTER_S:
                    trace(job.id, "director", "dropped", f"{lag:.0f}s behind live play", 0)
                    continue
                segments = await self.crew.produce(
                    job,
                    self.profile,
                    lambda agent, status, detail, ms, j=job.id: trace(j, agent, status, detail, ms),
                )
                for segment in segments:
                    await out.put({"type": "segment", **segment.to_dict()})
            await out.put({"type": "end", "state": self.state.snapshot()})

        async def guarded(coro, name: str) -> None:
            try:
                await coro
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # surface instead of hanging the stream
                log.exception("%s task failed", name)
                await out.put({"type": "error", "message": f"{name} failed: {type(exc).__name__}"})
                await out.put({"type": "end", "state": self.state.snapshot()})

        yield {
            "type": "hello",
            "match": self.match.meta(),
            "profile": self.profile.to_dict(),
            "llm": self.crew.runtime.status() if self.crew.runtime else {"provider": "offline"},
        }
        tasks = [
            asyncio.create_task(guarded(feed(), "feed")),
            asyncio.create_task(guarded(produce(), "producer")),
        ]
        try:
            while True:
                message = await out.get()
                yield message
                if message["type"] == "end":
                    break
        finally:
            for task in tasks:
                task.cancel()
