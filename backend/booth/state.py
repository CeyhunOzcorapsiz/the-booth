"""Shared broadcast state: the single source of truth every agent reads from.

``MatchState`` is updated one event at a time by the orchestrator. Agents never see raw future events, so
nothing they say can leak what has not happened yet.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

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
    last_event: MatchEvent | None = None
    possession: str | None = None
    _momentum: deque = field(default_factory=deque)

    # --- updates ---------------------------------------------------------------------------------------
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
                if event.end_x is not None and self._final_third(team, event.end_x):
                    t["final_third_entries"] += 1
                    self._push_momentum(event, MOMENTUM_WEIGHTS["pass"])
            case "shot":
                t["shots"] += 1
                p["shots"] += 1
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
            case "tackle" | "interception":
                t[f"{event.type}s"] += 1
                p[f"{event.type}s"] += 1
            case "offside":
                t["offsides"] += 1
            case "substitution":
                t["substitutions"] += 1
        if event.type in KEY_MOMENT_TYPES:
            self.key_moments.append(self._moment(event))
        self.possession = event.possession
        self.last_event = event
        self._trim_momentum(event)

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
        }
