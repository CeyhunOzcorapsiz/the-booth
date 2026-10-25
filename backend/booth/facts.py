"""The stats desk: the only place numbers come from.

Every tool call registers ``Fact`` objects on a ``FactSheet``. Writers may only use numbers that appear on
the sheet (or on the event itself), and the fact-checker enforces that rule before anything goes on air.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Annotated

from booth.state import FrozenState


@dataclass(frozen=True)
class Fact:
    id: str
    label: str
    value: str
    numbers: tuple[float, ...] = ()

    def to_dict(self) -> dict:
        return {"id": self.id, "label": self.label, "value": self.value}


@dataclass
class FactSheet:
    facts: dict[str, Fact] = field(default_factory=dict)

    def add(self, fact: Fact) -> Fact:
        self.facts.setdefault(fact.id, fact)
        return fact

    def numbers(self) -> set[float]:
        return {n for fact in self.facts.values() for n in fact.numbers}

    def to_list(self) -> list[dict]:
        return [fact.to_dict() for fact in self.facts.values()]

    def __len__(self) -> int:
        return len(self.facts)


class StatsDesk:
    """Read-only statistics over a frozen state. Each public method is also exposed as an agent tool."""

    def __init__(self, state: FrozenState, sheet: FactSheet | None = None):
        self.state = state
        self.sheet = sheet if sheet is not None else FactSheet()
        self.match = state.match

    def _team_name(self, team: str) -> str:
        return self.match.teams[team].name

    def _resolve_team(self, team: str) -> str:
        value = team.strip().lower()
        for key, t in self.match.teams.items():
            if value in (key, t.name.lower(), t.short.lower()):
                return key
        raise ValueError(f"Unknown team '{team}'. Use 'home' or 'away'.")

    def _resolve_player(self, player: str) -> str:
        value = player.strip().lower()
        for team in self.match.teams.values():
            for p in team.players:
                if value in (p.id.lower(), p.name.lower(), p.short_name.lower()):
                    return p.id
        raise ValueError(f"Unknown player '{player}'.")

    # --- tools -----------------------------------------------------------------------------------------
    def score(self) -> dict:
        """Current score and match minute."""
        snap = self.state.snapshot
        home, away = snap["score"]["home"], snap["score"]["away"]
        fact = self.sheet.add(
            Fact(
                "F-score",
                "Score",
                f"{self._team_name('home')} {home}-{away} {self._team_name('away')} ({snap['minute']})",
                (home, away),
            )
        )
        return {
            "fact_id": fact.id,
            "home": self._team_name("home"),
            "away": self._team_name("away"),
            "home_goals": home,
            "away_goals": away,
            "minute": snap["minute"],
        }

    def team_stats(self, team: Annotated[str, "'home' or 'away' (or the club name)"]) -> dict:
        """Full statistics line for one team so far: possession, shots, corners, cards and more."""
        key = self._resolve_team(team)
        line = self.state.snapshot["teams"][key]
        name = self._team_name(key)
        out = {"team": name}
        for stat, value in line.items():
            if stat == "chance_quality_total":
                continue
            label = stat.replace("_", " ")
            fact = self.sheet.add(Fact(f"F-{key}-{stat}", f"{name} {label}", str(value), (value,)))
            out[stat] = {"value": value, "fact_id": fact.id}
        return out

    def compare(
        self, stat: Annotated[str, "e.g. possession_pct, shots, shots_on_target, corners, fouls"]
    ) -> dict:
        """Compare one statistic between the two teams."""
        teams = self.state.snapshot["teams"]
        if stat not in teams["home"] or stat == "chance_quality_total":
            raise ValueError(f"Unknown stat '{stat}'.")
        out = {"stat": stat}
        for key in ("home", "away"):
            value = teams[key][stat]
            fact = self.sheet.add(
                Fact(
                    f"F-{key}-{stat}",
                    f"{self._team_name(key)} {stat.replace('_', ' ')}",
                    str(value),
                    (value,),
                )
            )
            out[self._team_name(key)] = {"value": value, "fact_id": fact.id}
        return out

    def player_stats(self, player: Annotated[str, "player id (e.g. H9) or name"]) -> dict:
        """Statistics for one player so far: passes, shots, goals, assists, tackles, cards."""
        pid = self._resolve_player(player)
        p = self.match.player(pid)
        counters = self.state.players.get(pid, {})
        out = {"player": p.name, "number": p.number, "team": self._team_name(p.team), "position": p.position}
        for stat in (
            "passes",
            "shots",
            "shots_on_target",
            "goals",
            "assists",
            "tackles",
            "interceptions",
            "fouls",
            "saves",
            "yellow_cards",
        ):
            value = int(counters.get(stat, 0))
            if value == 0 and stat not in ("goals", "shots"):
                continue
            fact = self.sheet.add(
                Fact(f"F-{pid}-{stat}", f"{p.name} {stat.replace('_', ' ')}", str(value), (value,))
            )
            out[stat] = {"value": value, "fact_id": fact.id}
        return out

    def momentum(self) -> dict:
        """Which side has been on top over the last five minutes (-1 away .. +1 home)."""
        value = self.state.snapshot["momentum"]
        leader = "home" if value > 0.15 else "away" if value < -0.15 else None
        label = self._team_name(leader) + " on top" if leader else "evenly balanced"
        fact = self.sheet.add(Fact("F-momentum", "Momentum (last 5 min)", label, ()))
        return {"fact_id": fact.id, "momentum": value, "summary": label}

    def key_moments(self) -> dict:
        """Goals, cards, penalties and substitutions so far, in order."""
        moments = self.state.snapshot["key_moments"]
        fact = self.sheet.add(
            Fact(
                "F-moments",
                "Key moments",
                "; ".join(
                    f"{m['minute']} {m['type'].replace('_', ' ')} {m['player'] or ''}".strip()
                    for m in moments
                )
                or "none yet",
                tuple(float(n) for m in moments for n in re.findall(r"\d+", m["minute"])),
            )
        )
        return {"fact_id": fact.id, "moments": moments}

    def as_tools(self) -> list:
        """Wrap the desk methods as Microsoft Agent Framework function tools."""
        from agent_framework import tool

        return [
            tool(fn)
            for fn in (
                self.score,
                self.team_stats,
                self.compare,
                self.player_stats,
                self.momentum,
                self.key_moments,
            )
        ]
