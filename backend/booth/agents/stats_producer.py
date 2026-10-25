"""The stats producer pulls the numbers that put a moment in context, using tools rather than memory."""

from __future__ import annotations

import json

from booth.agents.base import Job
from booth.facts import FactSheet, StatsDesk
from booth.llm import LLMRuntime, LLMUnavailable

INSTRUCTIONS = """You are the stats producer of The Booth, an AI broadcast crew covering a SYNTHETIC football
match between fictional clubs. For the moment you are given, call the tools to fetch the 2-4 statistics that
best put it in context for viewers. For goals and red cards, always check the storylines tool first. Never guess a number: if you did not get it from a tool, do not use it.
Then reply with a single on-screen graphic caption of at most 14 words using only tool results."""


class StatsProducer:
    name = "stats-producer"

    def __init__(self, runtime: LLMRuntime | None):
        self.runtime = runtime

    async def collect(self, job: Job, use_model: bool) -> tuple[FactSheet, str | None, str]:
        """Return (fact sheet, model caption or None, source)."""
        desk = StatsDesk(job.state)
        if use_model and self.runtime is not None:
            prompt = json.dumps(
                {"moment": moment_context(job), "score": job.state.snapshot["score"]}, default=str
            )
            try:
                caption = await self.runtime.run(
                    "stats_producer", INSTRUCTIONS, prompt, tools=desk.as_tools()
                )
                if len(desk.sheet) >= 2:
                    return desk.sheet, caption, "ai"
            except LLMUnavailable:
                pass
        self.default_selection(desk, job)
        return desk.sheet, None, "rules"

    @staticmethod
    def default_selection(desk: StatsDesk, job: Job) -> None:
        event = job.event
        desk.score()
        if event.type in ("half_time", "full_time"):
            desk.team_stats("home")
            desk.team_stats("away")
            desk.key_moments()
            desk.storylines()
            return
        if "stats" in job.kinds and "color" not in job.kinds:
            for stat in ("possession_pct", "shots", "shots_on_target", "corners"):
                desk.compare(stat)
            return
        if event.team:
            desk.team_stats(event.team)
        if event.type == "goal" and event.player:
            desk.player_stats(event.player)
        elif event.type in ("yellow_card", "red_card") and event.player:
            desk.player_stats(event.player)
        desk.momentum()
        if any(story["event_id"] == event.id for story in job.state.snapshot.get("storylines", [])):
            desk.storylines()


def moment_context(job: Job) -> dict:
    event = job.event
    match = job.state.match
    player = match.player(event.player)
    target = match.player(event.target)
    return {
        "minute": event.display_minute,
        "type": event.type,
        "outcome": event.outcome,
        "team": match.teams[event.team].name if event.team else None,
        "team_key": event.team,
        "player": player.name if player else None,
        "player_id": event.player,
        "target": target.name if target else None,
        "detail": event.detail,
    }
