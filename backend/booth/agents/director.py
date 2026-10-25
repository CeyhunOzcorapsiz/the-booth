"""The director decides what goes on air for each viewer, and in what form.

It is deliberately rule-based: it runs on every one of ~1,000 events per match, must answer in microseconds
and must be explainable ("why did the booth talk about this?"). The expensive model-backed agents only run
on the work it plans.
"""

from __future__ import annotations

from booth.agents.base import Job
from booth.profile import ViewerProfile
from booth.sim.match import MatchEvent
from booth.state import MatchState

BASE_IMPORTANCE = {
    "goal": 1.0,
    "full_time": 1.0,
    "half_time": 1.0,
    "red_card": 0.95,
    "penalty_awarded": 0.9,
    "kickoff": 0.6,
    "yellow_card": 0.6,
    "shot": 0.55,
    "stoppage_time": 0.5,
    "substitution": 0.45,
    "free_kick": 0.4,
    "corner": 0.35,
    "offside": 0.3,
    "foul": 0.25,
    "tackle": 0.08,
    "interception": 0.08,
    "pass": 0.03,
}
SPEAK_THRESHOLD = {"hype": 0.25, "calm": 0.3, "tactical": 0.25, "beginner": 0.3}
COLOR_THRESHOLD = {"hype": 0.75, "calm": 0.85, "tactical": 0.6, "beginner": 0.85}
MIN_GAP_S = 6.0  # minimum match seconds between routine lines
FOLLOW_GAP_S = 45.0  # how often to mention a followed player's routine touches
SPATIAL_GAP_S = 40.0  # accessibility guide: describe the ball at least this often
STATS_EVERY_S = 15 * 60  # tactical viewers get a stats check every 15 minutes
EXPLAINABLE = {
    "offside",
    "corner",
    "yellow_card",
    "red_card",
    "penalty_awarded",
    "free_kick",
    "stoppage_time",
    "substitution",
}


class Director:
    name = "director"

    def __init__(self, profile: ViewerProfile):
        self.profile = profile
        self._last_line = -1e9
        self._last_follow = -1e9
        self._last_spatial = -1e9
        self._last_stats = 0.0
        self._last_possession: str | None = None
        self._explained: set[str] = set()
        self._count = 0

    def importance(self, event: MatchEvent) -> float:
        score = BASE_IMPORTANCE.get(event.type, 0.1)
        if event.type == "shot":
            quality = event.detail.get("chance_quality", 0.0)
            score += 0.25 if event.outcome == "saved" and quality > 0.25 else 0.0
            score += 0.1 if event.detail.get("situation") == "penalty" else 0.0
            score += 0.05 if event.detail.get("ball_speed_kmh", 0) >= 105 else 0.0
        if event.type == "pass" and event.outcome == "complete" and event.detail.get("difficulty", 0) >= 80:
            score += 0.25  # a killer pass is worth a line even though passes usually aren't
        if self.profile.follow and self.profile.follow in (event.player, event.target):
            score += 0.35
        return round(min(score, 1.0), 2)

    def plan(self, event: MatchEvent, state: MatchState) -> Job | None:
        """Return the work to do for this event, or ``None`` to stay quiet."""
        style = self.profile.style
        importance = self.importance(event)
        clock = event.clock
        kinds: list[str] = []

        followed = self.profile.follow and self.profile.follow in (event.player, event.target)
        routine = importance < 0.6
        if importance >= SPEAK_THRESHOLD[style]:
            if not routine or clock - self._last_line >= MIN_GAP_S:
                if not (followed and routine and clock - self._last_follow < FOLLOW_GAP_S):
                    kinds.append("pbp")
        new_story = bool(state.new_storylines)
        if new_story:
            importance = max(importance, 0.9)  # the storyline agent flagged a narrative worth airing
        if (importance >= COLOR_THRESHOLD[style] or new_story) and event.type not in (
            "half_time",
            "full_time",
            "kickoff",
        ):
            kinds.append("color")
        if style == "beginner" and event.type in EXPLAINABLE and event.type not in self._explained:
            kinds.append("explain")
            self._explained.add(event.type)
        if event.type in ("half_time", "full_time"):
            kinds.append("recap")
        if style == "tactical" and clock - self._last_stats >= STATS_EVERY_S and event.type == "pass":
            kinds.append("stats")
            self._last_stats = clock
        if self.profile.accessible and not kinds and event.possession:
            changed = event.possession != self._last_possession
            if (changed and clock - self._last_spatial >= 8) or clock - self._last_spatial >= SPATIAL_GAP_S:
                kinds.append("spatial")

        if event.possession:
            self._last_possession = event.possession
        if not kinds:
            return None
        if "pbp" in kinds:
            self._last_line = clock
            if followed:
                self._last_follow = clock
        if "spatial" in kinds or "pbp" in kinds:
            self._last_spatial = clock
        self._count += 1
        return Job(
            id=f"J{self._count:04d}",
            event=event,
            kinds=tuple(kinds),
            importance=importance,
            state=state.freeze(),
        )
