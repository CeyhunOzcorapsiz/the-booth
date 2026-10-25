"""The storyline agent: remembers the match so the crew can talk about more than the last event.

A goal is just a goal to an agent that only sees one event. The storyline tracker watches the whole match
through the shared state and spots narratives a single moment can't show: comebacks, late winners, braces,
quick-fire goals, goals against the run of play and red cards. Each storyline is stored on the state with
the numbers behind it, so writers can use it and the fact-checker can verify it.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from booth.agents.phrases import LANGS, phrases, plural
from booth.sim.match import MatchEvent

if TYPE_CHECKING:
    from booth.state import MatchState

LATE_MINUTE = 85
QUICK_FIRE_S = 6 * 60
AGAINST_THE_RUN_PCT = 40
RHYTHM_WINDOW_S = 300
RHYTHM_MIN_GAP_S = 10 * 60
CONTROL_PASS_SHARE = 62


class RhythmMeter:
    """Control vs chaos over the last five minutes, from possession changes and who is passing.

    Calibrated on the simulator: a typical five minutes has about 7 changes of possession; 5 or fewer is a
    controlled spell, 10 or more is end-to-end. Announcements are at least ten minutes apart.
    """

    def __init__(self):
        self._window: deque = deque()
        self._possession: str | None = None

    def observe(self, event: MatchEvent) -> None:
        changed = bool(self._possession and event.possession and event.possession != self._possession)
        if event.possession:
            self._possession = event.possession
        passer = event.team if event.type == "pass" else None
        self._window.append((event.period, event.clock, changed, passer))
        while self._window and (
            self._window[0][0] != event.period or event.clock - self._window[0][1] > RHYTHM_WINDOW_S
        ):
            self._window.popleft()

    def snapshot(self) -> dict:
        changes = sum(1 for _, _, changed, _ in self._window if changed)
        passes = {"home": 0, "away": 0}
        for *_, passer in self._window:
            if passer:
                passes[passer] += 1
        total = passes["home"] + passes["away"]
        chaos = int(max(0, min(100, round((changes - 4) / 8 * 100))))
        leader = max(passes, key=passes.get) if total else None
        share = round(100 * passes[leader] / total) if leader else 0
        label = "chaotic" if chaos >= 65 else "controlled" if chaos <= 12 else "open"
        controller = leader if label == "controlled" and share >= CONTROL_PASS_SHARE else None
        return {
            "chaos": chaos,
            "label": label,
            "changes_5min": changes,
            "passes_per_min": round(total / (RHYTHM_WINDOW_S / 60), 1),
            "pass_share_pct": share,
            "controller": controller,
        }


@dataclass(frozen=True)
class Storyline:
    id: str
    kind: str
    event_id: str
    minute: str
    team: str | None
    player: str | None
    texts: dict[str, str]
    numbers: tuple[float, ...]

    @property
    def en(self) -> str:
        return self.texts["en"]

    @property
    def tr(self) -> str:
        return self.texts["tr"]

    def to_dict(self) -> dict:
        return {**asdict(self), "en": self.en, "tr": self.tr}

    def text(self, lang: str) -> str:
        return self.texts.get(lang, self.en)


class StorylineTracker:
    name = "storyline"

    def __init__(self):
        self.storylines: list[Storyline] = []
        self.rhythm = RhythmMeter()
        self._rhythm_announced: tuple[str, str | None] | None = None
        self._rhythm_at = -1e9
        self._max_deficit = {"home": 0, "away": 0}
        self._last_goal: dict[str, tuple[int, float]] = {}

    def observe(self, event: MatchEvent, state: MatchState) -> list[Storyline]:
        """Update after ``state`` has applied ``event``; returns storylines that started with this event."""
        found: list[Storyline] = []
        self.rhythm.observe(event)
        found += self._rhythm(event, state)
        if event.type == "goal" and event.team:
            found += self._goal(event, state)
        elif event.type == "red_card" and event.team:
            name = state.match.teams[event.team].name
            found.append(self._story(event, "down_to_ten", event.team, None, {"name": name}, (10,)))
        for team in ("home", "away"):
            other = "away" if team == "home" else "home"
            self._max_deficit[team] = max(self._max_deficit[team], state.score[other] - state.score[team])
        self.storylines += found
        return found

    def _goal(self, event: MatchEvent, state: MatchState) -> list[Storyline]:
        team, other = event.team, "away" if event.team == "home" else "home"
        match = state.match
        name = match.teams[team].name
        h, a = state.score["home"], state.score["away"]
        score = f"{h}-{a}"
        lead = state.score[team] - state.score[other]
        was = lead - 1
        stories: list[Storyline] = []
        deficit = self._max_deficit[team]

        if lead >= 0 and deficit >= 2 and not self._has(team, "comeback"):
            stories.append(
                self._story(
                    event,
                    "comeback",
                    team,
                    None,
                    {"name": name, "deficit": deficit, "score": score},
                    (deficit, h, a),
                )
            )
        elif lead == 1 and was == 0 and deficit >= 1 and not self._has(team, "turnaround"):
            stories.append(
                self._story(
                    event,
                    "turnaround",
                    team,
                    None,
                    {"name": name, "score": score},
                    (h, a),
                )
            )

        if event.minute >= LATE_MINUTE and event.period == 2:
            if lead == 0:
                stories.append(
                    self._story(
                        event,
                        "late_equalizer",
                        team,
                        None,
                        {"name": name, "score": score, "minute": event.display_minute},
                        (h, a, event.minute),
                    )
                )
            elif lead == 1 and was == 0:
                stories.append(
                    self._story(
                        event,
                        "late_winner",
                        team,
                        None,
                        {"name": name, "score": score, "minute": event.display_minute},
                        (h, a, event.minute),
                    )
                )

        player = match.player(event.player)
        goals = state.players[event.player]["goals"] if event.player else 0
        if player and goals >= 2:
            kind = "hat_trick" if goals == 3 else "brace" if goals == 2 else "haul"
            params = {"player": player.short_name, "goals": goals}
            stories.append(self._story(event, kind, team, event.player, params, (goals,)))

        previous = self._last_goal.get(team)
        if previous and previous[0] == event.period and event.clock - previous[1] <= QUICK_FIRE_S:
            minutes = max(1, round((event.clock - previous[1]) / 60))
            stories.append(
                self._story(
                    event,
                    "quick_fire",
                    team,
                    None,
                    {"name": name, "minutes": minutes},
                    (minutes,),
                )
            )
        self._last_goal[team] = (event.period, event.clock)
        if any(st.kind == "late_winner" for st in stories):  # says everything "turnaround" would
            stories = [st for st in stories if st.kind != "turnaround"]

        possession = state.possession_pct()[team]
        if possession < AGAINST_THE_RUN_PCT and event.minute > 15:
            stories.append(
                self._story(
                    event,
                    "against_the_run",
                    team,
                    None,
                    {"name": name, "possession": possession},
                    (possession,),
                )
            )
        return stories

    def _rhythm(self, event: MatchEvent, state: MatchState) -> list[Storyline]:
        """Announce a change in the rhythm of the game (at most every eight minutes, after the opening spell)."""
        if event.minute < 12:
            return []
        r = self.rhythm.snapshot()
        key = (r["label"], r["controller"])
        absolute = event.clock + (10_000 if event.period == 2 else 0)
        if key == self._rhythm_announced or absolute - self._rhythm_at < RHYTHM_MIN_GAP_S:
            return []
        if r["label"] == "controlled" and r["controller"]:
            name = state.match.teams[r["controller"]].name
            story = self._story(
                event,
                "control",
                r["controller"],
                None,
                {"name": name, "share": r["pass_share_pct"], "changes": r["changes_5min"]},
                (r["pass_share_pct"], r["changes_5min"]),
            )
        elif r["label"] == "chaotic":
            story = self._story(
                event,
                "chaos",
                None,
                None,
                {"changes": r["changes_5min"]},
                (r["changes_5min"],),
            )
        else:
            return []
        self._rhythm_announced, self._rhythm_at = key, absolute
        return [story]

    def _has(self, team: str, kind: str) -> bool:
        return any(s.team == team and s.kind == kind for s in self.storylines)

    @staticmethod
    def _story(
        event: MatchEvent, kind: str, team: str | None, player: str | None, params: dict, numbers: tuple
    ) -> Storyline:
        values = {**params, "s_changes": plural(params.get("changes", 2))}
        return Storyline(
            id=f"S-{event.id}-{kind}",
            kind=kind,
            event_id=event.id,
            minute=event.display_minute,
            team=team,
            player=player,
            texts={lang: phrases(lang)["stories"][kind].format(**values) for lang in LANGS},
            numbers=tuple(float(n) for n in numbers),
        )
