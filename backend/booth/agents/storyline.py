"""The storyline agent: remembers the match so the crew can talk about more than the last event.

A goal is just a goal to an agent that only sees one event. The storyline tracker watches the whole match
through the shared state and spots narratives a single moment can't show: comebacks, late winners, braces,
quick-fire goals, goals against the run of play and red cards. Each storyline is stored on the state with
the numbers behind it, so writers can use it and the fact-checker can verify it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from booth.sim.match import MatchEvent

if TYPE_CHECKING:
    from booth.state import MatchState

LATE_MINUTE = 85
QUICK_FIRE_S = 6 * 60
AGAINST_THE_RUN_PCT = 40


@dataclass(frozen=True)
class Storyline:
    id: str
    kind: str
    event_id: str
    minute: str
    team: str | None
    player: str | None
    en: str
    tr: str
    numbers: tuple[float, ...]

    def to_dict(self) -> dict:
        return asdict(self)

    def text(self, lang: str) -> str:
        return self.tr if lang == "tr" else self.en


class StorylineTracker:
    name = "storyline"

    def __init__(self):
        self.storylines: list[Storyline] = []
        self._max_deficit = {"home": 0, "away": 0}
        self._last_goal: dict[str, tuple[int, float]] = {}

    def observe(self, event: MatchEvent, state: MatchState) -> list[Storyline]:
        """Update after ``state`` has applied ``event``; returns storylines that started with this event."""
        found: list[Storyline] = []
        if event.type == "goal" and event.team:
            found += self._goal(event, state)
        elif event.type == "red_card" and event.team:
            name = state.match.teams[event.team].name
            found.append(
                self._story(
                    event,
                    "down_to_ten",
                    event.team,
                    None,
                    f"{name} are down to 10 for the rest of the match.",
                    f"{name} maçın kalanında 10 kişi.",
                    (10,),
                )
            )
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
                    f"{name} were {deficit} goals down and have fought back to {score}.",
                    f"{name} {deficit} gol gerideydi, skor şimdi {score}.",
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
                    f"{name} were behind earlier and now lead {score}.",
                    f"{name} geriye düşmüştü, şimdi {score} önde.",
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
                        f"Late drama at {event.display_minute}: {name} level it at {score}.",
                        f"Son dakika dramı ({event.display_minute}): {name} skoru {score} yaptı.",
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
                        f"A late winner? {name} lead {score} at {event.display_minute}.",
                        f"Galibiyet golü mü? ({event.display_minute}) {name} {score} öne geçti.",
                        (h, a, event.minute),
                    )
                )

        player = match.player(event.player)
        goals = state.players[event.player]["goals"] if event.player else 0
        if player and goals >= 2:
            kind = "hat_trick" if goals == 3 else "brace" if goals == 2 else "haul"
            en = (
                f"Hat-trick for {player.short_name}!"
                if goals == 3
                else f"That's {goals} goals today for {player.short_name}."
            )
            tr = (
                f"{player.short_name} hat-trick yaptı!"
                if goals == 3
                else f"{player.short_name} bugün {goals} gol attı."
            )
            stories.append(self._story(event, kind, team, event.player, en, tr, (goals,)))

        previous = self._last_goal.get(team)
        if previous and previous[0] == event.period and event.clock - previous[1] <= QUICK_FIRE_S:
            minutes = max(1, round((event.clock - previous[1]) / 60))
            stories.append(
                self._story(
                    event,
                    "quick_fire",
                    team,
                    None,
                    f"{name} have scored twice in {minutes} minutes.",
                    f"{name} {minutes} dakikada iki gol buldu.",
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
                    f"{name} score despite having only {possession}% of the ball.",
                    f"{name}, topa yalnızca %{possession} sahipken gol buldu.",
                    (possession,),
                )
            )
        return stories

    def _has(self, team: str, kind: str) -> bool:
        return any(s.team == team and s.kind == kind for s in self.storylines)

    @staticmethod
    def _story(
        event: MatchEvent, kind: str, team: str | None, player: str | None, en: str, tr: str, numbers: tuple
    ) -> Storyline:
        return Storyline(
            id=f"S-{event.id}-{kind}",
            kind=kind,
            event_id=event.id,
            minute=event.display_minute,
            team=team,
            player=player,
            en=en,
            tr=tr,
            numbers=tuple(float(n) for n in numbers),
        )
