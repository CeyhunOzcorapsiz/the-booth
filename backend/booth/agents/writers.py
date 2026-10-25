"""Writers: play-by-play, analyst (colour) and recap editor.

Model-backed writers produce an English "world feed" line; the localizer adapts it per viewer language.
When the model is unavailable, the templates produce text directly in English or Turkish.
"""

from __future__ import annotations

import json

from booth.agents import templates
from booth.agents.base import Job
from booth.agents.stats_producer import moment_context
from booth.facts import FactSheet
from booth.llm import LLMRuntime
from booth.profile import ViewerProfile

STYLE_GUIDES = {
    "hype": "energetic and vivid, like a big-night TV commentator",
    "calm": "measured and clear, like a radio commentator",
    "tactical": "focused on space, positioning and the shape of the play",
    "beginner": "friendly and simple; avoid jargon or explain it in a few words",
}
GROUND_RULES = """The match is SYNTHETIC and the clubs and players are fictional. Use only names and numbers
present in the input. Never invent statistics, player intent, emotions, injuries or history. No emojis or
hashtags. Return only the text to be read on air."""

PBP_INSTRUCTIONS = (
    "You are the play-by-play commentator of The Booth. Write ONE line (max 25 words) in English "
    "describing the moment. " + GROUND_RULES
)
COLOR_INSTRUCTIONS = (
    "You are the analyst (co-commentator) of The Booth. Write 1-2 sentences (max 45 words) in "
    "English that add context to the moment, using numbers ONLY from the facts list. " + GROUND_RULES
)
RECAP_INSTRUCTIONS = (
    "You are the recap editor of The Booth. Write a {kind} of 3-4 sentences (max 90 words) in "
    "English from the snapshot and facts: result, goals, and how the game was played. " + GROUND_RULES
)


def _style(profile: ViewerProfile) -> str:
    guide = STYLE_GUIDES[profile.style]
    if profile.accessible:
        guide += ". The listener cannot see the pitch, so say where the action is using the location provided"
    return guide


class Writers:
    def __init__(self, runtime: LLMRuntime | None):
        self.runtime = runtime

    def _context(self, job: Job, profile: ViewerProfile, sheet: FactSheet | None = None) -> dict:
        event = job.event
        context = {
            "style": _style(profile),
            "moment": moment_context(job),
            "score": job.state.snapshot["score"],
            "clubs": {k: t.name for k, t in job.state.match.teams.items()},
            "location": templates.describe_location(event.x, event.y, event.team, "en"),
        }
        followed = job.state.match.player(profile.follow) if profile.follow else None
        if followed:
            context["viewer_follows"] = followed.name
        if sheet is not None:
            context["facts"] = sheet.to_list()
        return context

    async def write_model(
        self, kind: str, job: Job, profile: ViewerProfile, sheet: FactSheet, feedback: list[str] | None = None
    ) -> str:
        if kind == "pbp":
            instructions, context = PBP_INSTRUCTIONS, self._context(job, profile)
        elif kind == "color":
            instructions, context = COLOR_INSTRUCTIONS, self._context(job, profile, sheet)
        else:
            label = "full-time report" if job.event.type == "full_time" else "half-time report"
            instructions = RECAP_INSTRUCTIONS.format(kind=label)
            context = self._context(job, profile, sheet) | {"snapshot": job.state.snapshot}
        prompt = json.dumps(context, ensure_ascii=False, default=str)
        if feedback:
            prompt += (
                "\n\nYour previous draft was rejected by the fact-checker: "
                + "; ".join(feedback)
                + ". Rewrite it and fix exactly these problems."
            )
        return await self.runtime.run(kind, instructions, prompt)

    @staticmethod
    def write_template(kind: str, job: Job, profile: ViewerProfile, sheet: FactSheet, lang: str) -> str:
        event, match, snapshot = job.event, job.state.match, job.state.snapshot
        if kind == "pbp":
            text = templates.play_by_play(event, match, snapshot["score"], lang, profile.style)
            if profile.accessible and event.type in ("shot", "foul", "free_kick", "corner", "goal"):
                text += (
                    " " + templates.describe_location(event.x, event.y, event.team, lang).capitalize() + "."
                )
            return text
        if kind == "color":
            return templates.color(event, match, sheet, lang)
        if kind == "recap":
            return templates.recap(match, snapshot, lang, final=event.type == "full_time")
        if kind == "stats":
            return templates.stat_caption(sheet, lang)
        if kind == "explain":
            return templates.explain(event.type, lang) or ""
        if kind == "spatial":
            return templates.spatial(event, match, lang)
        raise ValueError(f"unknown kind {kind}")
