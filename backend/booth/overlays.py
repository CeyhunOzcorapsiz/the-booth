"""Timed, machine-readable overlay cues for broadcast graphics.

A graphics engine (lower thirds, score bug, stat cards, player tags) can render these in sync with the
match clock. Every cue carries the event and fact ids it was built from, and only uses data from the shared
state, so overlays are as verifiable as the commentary. See docs/OVERLAYS.md for the schema.
"""

from __future__ import annotations

from booth.sim.match import Match, MatchEvent
from booth.sim.tracking import tracking_for
from booth.state import MatchState

SCHEMA_VERSION = "1.0"
STAT_CARD_EVERY_S = 15 * 60
FAST_SHOT_KMH = 100
KILLER_PASS = 80
LONG_BALL_M = 45
SPRINT_TAG_KMH = 30

LABELS = {
    "en": {
        "goal": "GOAL",
        "yellow_card": "YELLOW CARD",
        "red_card": "RED CARD",
        "substitution": "SUBSTITUTION",
        "penalty_awarded": "PENALTY",
        "assist": "assist",
        "on": "on",
        "off": "off",
        "half_time": "HALF TIME",
        "full_time": "FULL TIME",
        "stats": "MATCH STATS",
        "killer": "killer pass",
        "long": "long ball",
        "possession": "Possession %",
        "shots": "Shots",
        "on_target": "On target",
        "pass_acc": "Pass accuracy %",
        "storyline": "STORYLINE",
        "distance": "Distance (km)",
        "sprint": "sprint",
    },
    "tr": {
        "goal": "GOL",
        "yellow_card": "SARI KART",
        "red_card": "KIRMIZI KART",
        "substitution": "OYUNCU DEĞİŞİKLİĞİ",
        "penalty_awarded": "PENALTI",
        "assist": "asist",
        "on": "giren",
        "off": "çıkan",
        "half_time": "İLK YARI SONU",
        "full_time": "MAÇ SONU",
        "stats": "MAÇ İSTATİSTİKLERİ",
        "killer": "kilit pas",
        "long": "uzun top",
        "possession": "Topa sahip olma %",
        "shots": "Şut",
        "on_target": "İsabetli şut",
        "pass_acc": "Pas isabeti %",
        "storyline": "HİKÂYE",
        "distance": "Koşu mesafesi (km)",
        "sprint": "sprint",
    },
}


class OverlayBuilder:
    """Turns the event stream into overlay cues. Call ``observe`` after the state has applied each event."""

    def __init__(self, match: Match, lang: str = "en"):
        self.match = match
        self.lang = lang if lang in LABELS else "en"
        self.text = LABELS[self.lang]
        self._count = 0
        self._last_stats = 0.0

    def _cue(
        self,
        event: MatchEvent,
        kind: str,
        duration_s: float,
        priority: int,
        payload: dict,
        evidence: list[str],
    ) -> dict:
        self._count += 1
        return {
            "id": f"C{self._count:04d}",
            "at": {"period": event.period, "clock_s": event.clock, "display_minute": event.display_minute},
            "duration_s": duration_s,
            "type": kind,
            "priority": priority,
            "payload": payload,
            "evidence": evidence,
        }

    def _name(self, pid: str | None) -> dict | None:
        player = self.match.player(pid)
        if not player:
            return None
        return {
            "id": player.id,
            "name": player.name,
            "number": player.number,
            "team": self.match.teams[player.team].name,
        }

    def _score_bug(self, event: MatchEvent, state: MatchState) -> dict:
        score = state.score
        return self._cue(
            event,
            "score_bug",
            0,
            1,
            {
                "home": self.match.teams["home"].short,
                "away": self.match.teams["away"].short,
                "home_goals": score["home"],
                "away_goals": score["away"],
                "minute": event.display_minute,
            },
            [event.id],
        )

    def observe(self, event: MatchEvent, state: MatchState) -> list[dict]:
        t = self.text
        cues: list[dict] = []
        d = event.detail
        if event.type in ("kickoff", "goal", "half_time", "full_time"):
            cues.append(self._score_bug(event, state))
        if event.type == "goal":
            assist = self._name(event.target)
            line2 = [f"{t['assist']}: {assist['name']}"] if assist else []
            cues.append(
                self._cue(
                    event,
                    "lower_third",
                    8,
                    3,
                    {
                        "title": t["goal"],
                        "player": self._name(event.player),
                        "lines": line2,
                        "team": self.match.teams[event.team].name,
                    },
                    [event.id],
                )
            )
        elif event.type in ("yellow_card", "red_card", "penalty_awarded"):
            cues.append(
                self._cue(
                    event,
                    "lower_third",
                    6,
                    3 if event.type != "yellow_card" else 2,
                    {
                        "title": t[event.type],
                        "player": self._name(event.player),
                        "lines": [],
                        "team": self.match.teams[event.team].name,
                    },
                    [event.id],
                )
            )
        elif event.type == "substitution":
            on, off = self._name(d.get("on")), self._name(d.get("off"))
            cues.append(
                self._cue(
                    event,
                    "lower_third",
                    6,
                    2,
                    {
                        "title": t["substitution"],
                        "player": on,
                        "lines": [f"{t['on']}: {on['name']}", f"{t['off']}: {off['name']}"]
                        if on and off
                        else [],
                        "team": self.match.teams[event.team].name,
                    },
                    [event.id],
                )
            )
        elif event.type == "shot" and d.get("ball_speed_kmh", 0) >= FAST_SHOT_KMH:
            cues.append(
                self._cue(
                    event,
                    "player_tag",
                    4,
                    2,
                    {
                        "player": self._name(event.player),
                        "metric": "ball_speed_kmh",
                        "value": d["ball_speed_kmh"],
                        "label": f"{d['ball_speed_kmh']} km/h",
                        "x": event.x,
                        "y": event.y,
                    },
                    [event.id],
                )
            )
        elif event.type == "pass" and event.outcome == "complete":
            if d.get("difficulty", 0) >= KILLER_PASS:
                cues.append(
                    self._cue(
                        event,
                        "player_tag",
                        4,
                        1,
                        {
                            "player": self._name(event.player),
                            "metric": "difficulty",
                            "value": d["difficulty"],
                            "label": f"{t['killer']} {d['difficulty']}/100",
                            "x": event.x,
                            "y": event.y,
                        },
                        [event.id],
                    )
                )
            elif d.get("pass_distance_m", 0) >= LONG_BALL_M:
                cues.append(
                    self._cue(
                        event,
                        "player_tag",
                        4,
                        1,
                        {
                            "player": self._name(event.player),
                            "metric": "pass_distance_m",
                            "value": d["pass_distance_m"],
                            "label": f"{t['long']} {round(d['pass_distance_m'])} m",
                            "x": event.x,
                            "y": event.y,
                        },
                        [event.id],
                    )
                )

        if event.type in ("tackle", "interception", "shot") and event.player:
            run = tracking_for(self.match).speed_at(event.player, event.period, event.clock)
            if run >= SPRINT_TAG_KMH and not any(c["type"] == "player_tag" for c in cues):
                cues.append(
                    self._cue(
                        event,
                        "player_tag",
                        4,
                        2,
                        {
                            "player": self._name(event.player),
                            "metric": "running_speed_kmh",
                            "value": run,
                            "label": f"{t['sprint']} {run:.0f} km/h",
                            "x": event.x,
                            "y": event.y,
                        },
                        [event.id],
                    )
                )

        for story in state.new_storylines:
            cues.append(
                self._cue(
                    event,
                    "storyline_banner",
                    10,
                    2,
                    {
                        "title": t["storyline"],
                        "kind": story.kind,
                        "text": story.text(self.lang),
                    },
                    [event.id, story.id],
                )
            )

        absolute = event.clock + (5400 if event.period == 2 else 0)
        if event.type in ("half_time", "full_time") or (
            event.type == "pass" and absolute - self._last_stats >= STAT_CARD_EVERY_S
        ):
            self._last_stats = absolute
            cues.append(self._stat_card(event, state))
        return cues

    def _stat_card(self, event: MatchEvent, state: MatchState) -> dict:
        t = self.text
        h, a = state.team_line("home"), state.team_line("away")
        rows = [
            (t["possession"], h["possession_pct"], a["possession_pct"], "possession_pct"),
            (t["shots"], h["shots"], a["shots"], "shots"),
            (t["on_target"], h["shots_on_target"], a["shots_on_target"], "shots_on_target"),
            (t["pass_acc"], h["pass_accuracy_pct"], a["pass_accuracy_pct"], "pass_accuracy_pct"),
            (t["distance"], h["distance_km"], a["distance_km"], "distance_km"),
        ]
        title = t.get(event.type, t["stats"]) if event.type in ("half_time", "full_time") else t["stats"]
        return self._cue(
            event,
            "stat_card",
            10,
            2,
            {
                "title": title,
                "home": self.match.teams["home"].name,
                "away": self.match.teams["away"].name,
                "rows": [{"label": label, "home": hv, "away": av} for label, hv, av, _ in rows],
            },
            [event.id] + [f"F-{side}-{key}" for *_, key in rows for side in ("home", "away")],
        )


def build_cues(match: Match, lang: str = "en", from_minute: float = 0, to_minute: float = 200) -> list[dict]:
    """All cues for a match (replaying the events through a fresh state)."""
    state = MatchState(match)
    builder = OverlayBuilder(match, lang)
    cues: list[dict] = []
    for event in match.events:
        state.apply(event)
        for cue in builder.observe(event, state):
            if from_minute * 60 <= event.clock <= to_minute * 60:
                cues.append(cue)
    return cues
