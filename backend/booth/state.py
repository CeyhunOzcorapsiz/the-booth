"""Shared broadcast state: the single source of truth every agent reads from.

``MatchState`` is updated one event at a time by the orchestrator. Agents never see raw future events, so
nothing they say can leak what has not happened yet.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

from booth.agents.storyline import Storyline, StorylineTracker
from booth.sim.match import Match, MatchEvent

MOMENTUM_WINDOW_S = 300
MOMENTUM_WEIGHTS = {"pass": 0.4, "corner": 2.0, "free_kick": 1.0, "goal": 6.0, "penalty_awarded": 3.0}
KEY_MOMENT_TYPES = {
    "goal",
    "red_card",
    "yellow_card",
    "penalty_awarded",
    "substitution",
    "half_time",
    "full_time",
}


def match_position(minute: float, period: int | None = None) -> tuple[int, float]:
    """Sortable (period, clock) for a broadcast minute.

    The clock is continuous within a half but the second half restarts at 45:00, so a minute between 45 and
    the end of first-half stoppage time is ambiguous. Without an explicit ``period``, minutes above 45 are
    read as second half (46' means the 46th minute, not 45+1').
    """
    if period is None:
        period = 2 if minute > 45 else 1
    if period not in (1, 2):
        raise ValueError("period must be 1 or 2")
    return period, max(0.0, minute) * 60


@dataclass(frozen=True)
class FrozenState:
    match: Match
    snapshot: dict
    players: dict[str, dict[str, int]]
    event: MatchEvent | None


def _team_counters() -> dict[str, float]:
    return defaultdict(float)


def _player_counters() -> dict[str, int]:
    return defaultdict(int)


@dataclass
class MatchState:
    match: Match
    score: dict[str, int] = field(default_factory=lambda: {"home": 0, "away": 0})
    teams: dict[str, dict[str, float]] = field(
        default_factory=lambda: {"home": _team_counters(), "away": _team_counters()}
    )
    players: dict[str, dict[str, int]] = field(default_factory=lambda: defaultdict(_player_counters))
    key_moments: list[dict] = field(default_factory=list)
    story: StorylineTracker = field(default_factory=StorylineTracker)
    on_pitch: dict[str, list[str | None]] = field(default_factory=dict)  # slot order, None = sent off
    new_storylines: list[Storyline] = field(default_factory=list)
    last_event: MatchEvent | None = None
    possession: str | None = None
    _momentum: deque = field(default_factory=deque)

    # --- updates ---------------------------------------------------------------------------------------
    def __post_init__(self) -> None:
        if not self.on_pitch:
            self.on_pitch = {
                key: [p.id for p in team.players if p.starter] for key, team in self.match.teams.items()
            }

    def apply(self, event: MatchEvent) -> None:
        if self.last_event is not None and self.possession and event.period == self.last_event.period:
            self.teams[self.possession]["possession_s"] += max(0.0, event.clock - self.last_event.clock)
        team, player = event.team, event.player
        t = self.teams[team] if team else None
        p = self.players[player] if player else None
        match event.type:
            case "pass":
                t["passes"] += 1
                p["passes"] += 1
                if event.outcome == "complete":
                    t["passes_completed"] += 1
                    p["passes_completed"] += 1
                    t["pass_difficulty_sum"] += event.detail.get("difficulty", 0)
                    if event.detail.get("difficulty", 0) >= 65:
                        t["hard_passes_completed"] += 1
                        p["hard_passes_completed"] += 1
                if event.end_x is not None and self._final_third(team, event.end_x):
                    t["final_third_entries"] += 1
                    self._push_momentum(event, MOMENTUM_WEIGHTS["pass"])
            case "shot":
                t["shots"] += 1
                p["shots"] += 1
                speed = event.detail.get("ball_speed_kmh", 0)
                t["fastest_shot_kmh"] = max(t["fastest_shot_kmh"], speed)
                p["fastest_shot_kmh"] = max(p["fastest_shot_kmh"], speed)
                if event.outcome in ("goal", "saved"):
                    t["shots_on_target"] += 1
                    p["shots_on_target"] += 1
                if event.outcome == "saved":
                    self.teams[self._other(team)]["saves"] += 1
                    keeper = event.detail.get("goalkeeper")
                    if keeper:
                        self.players[keeper]["saves"] += 1
                t["chance_quality"] += event.detail.get("chance_quality", 0.0)
                self._push_momentum(event, 4.0 if event.outcome in ("goal", "saved") else 2.5)
            case "goal":
                self.score[team] += 1
                p["goals"] += 1
                if event.target:
                    self.players[event.target]["assists"] += 1
                self._push_momentum(event, MOMENTUM_WEIGHTS["goal"])
            case "corner" | "free_kick" | "penalty_awarded":
                t[f"{event.type}s"] += 1
                self._push_momentum(event, MOMENTUM_WEIGHTS[event.type])
            case "foul":
                t["fouls"] += 1
                p["fouls"] += 1
            case "yellow_card" | "red_card":
                t[f"{event.type}s"] += 1
                p[f"{event.type}s"] += 1
                if event.type == "red_card" and player in self.on_pitch[team]:
                    # keep the slot empty so everyone else keeps their position in the shape
                    self.on_pitch[team][self.on_pitch[team].index(player)] = None
            case "tackle" | "interception":
                t[f"{event.type}s"] += 1
                p[f"{event.type}s"] += 1
            case "offside":
                t["offsides"] += 1
            case "substitution":
                t["substitutions"] += 1
                lineup = self.on_pitch[team]
                off, on = event.detail.get("off"), event.detail.get("on")
                if off in lineup:
                    lineup[lineup.index(off)] = on  # the substitute takes the same slot
        if event.type in KEY_MOMENT_TYPES:
            self.key_moments.append(self._moment(event))
        self.possession = event.possession
        self.last_event = event
        self._trim_momentum(event)
        self.new_storylines = self.story.observe(event, self)

    def _final_third(self, team: str, x: float) -> bool:
        return x > 70 if team == "home" else x < 35

    @staticmethod
    def _other(team: str) -> str:
        return "away" if team == "home" else "home"

    def _push_momentum(self, event: MatchEvent, weight: float) -> None:
        self._momentum.append((event.period, event.clock, event.team, weight))

    def _trim_momentum(self, event: MatchEvent) -> None:
        while self._momentum and (
            self._momentum[0][0] != event.period or event.clock - self._momentum[0][1] > MOMENTUM_WINDOW_S
        ):
            self._momentum.popleft()

    def _moment(self, event: MatchEvent) -> dict:
        player = self.match.player(event.player)
        target = self.match.player(event.target)
        return {
            "event_id": event.id,
            "type": event.type,
            "minute": event.display_minute,
            "team": event.team,
            "player": player.name if player else None,
            "target": target.name if target else None,
            "score": f"{self.score['home']}-{self.score['away']}",
        }

    # --- reads -----------------------------------------------------------------------------------------
    @property
    def minute(self) -> str:
        return self.last_event.display_minute if self.last_event else "0'"

    def possession_pct(self) -> dict[str, int]:
        home, away = self.teams["home"]["possession_s"], self.teams["away"]["possession_s"]
        total = home + away
        if total == 0:
            return {"home": 50, "away": 50}
        home_pct = round(100 * home / total)
        return {"home": home_pct, "away": 100 - home_pct}

    def momentum(self) -> float:
        """-1 (away dominant) .. +1 (home dominant) over the last five minutes."""
        home = sum(w for *_, team, w in self._momentum if team == "home")
        away = sum(w for *_, team, w in self._momentum if team == "away")
        return round((home - away) / (home + away + 1.0), 2)

    def team_line(self, team: str) -> dict:
        t = self.teams[team]
        return {
            "goals": self.score[team],
            "possession_pct": self.possession_pct()[team],
            "shots": int(t["shots"]),
            "shots_on_target": int(t["shots_on_target"]),
            "corners": int(t["corners"]),
            "fouls": int(t["fouls"]),
            "yellow_cards": int(t["yellow_cards"]),
            "red_cards": int(t["red_cards"]),
            "passes": int(t["passes"]),
            "pass_accuracy_pct": round(100 * t["passes_completed"] / t["passes"]) if t["passes"] else 0,
            "avg_pass_difficulty": round(t["pass_difficulty_sum"] / t["passes_completed"])
            if t["passes_completed"]
            else 0,
            "hard_passes_completed": int(t["hard_passes_completed"]),
            "fastest_shot_kmh": int(t["fastest_shot_kmh"]),
            "saves": int(t["saves"]),
            "offsides": int(t["offsides"]),
            "final_third_entries": int(t["final_third_entries"]),
            "chance_quality_total": round(t["chance_quality"], 2),
        }

    def freeze(self) -> FrozenState:
        """Copy what agents may read at this instant, so later events cannot change their inputs."""
        return FrozenState(
            match=self.match,
            snapshot=self.snapshot(),
            players={pid: dict(counters) for pid, counters in self.players.items()},
            event=self.last_event,
        )

    def snapshot(self) -> dict:
        return {
            "minute": self.minute,
            "period": self.last_event.period if self.last_event else 1,
            "score": dict(self.score),
            "possession": self.possession,
            "momentum": self.momentum(),
            "teams": {team: self.team_line(team) for team in ("home", "away")},
            "key_moments": self.key_moments[-12:],
            "storylines": [s.to_dict() for s in self.story.storylines[-8:]],
            "rhythm": self.story.rhythm.snapshot(),
            "on_pitch": {team: list(ids) for team, ids in self.on_pitch.items()},
        }
