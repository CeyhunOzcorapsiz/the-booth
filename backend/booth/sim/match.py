"""Seeded synthetic football match generator.

Everything produced here is fictional: clubs, players and events come from a seed, never from real
match data. Coordinates are metres on a 105 x 68 pitch and the home side always attacks towards x = 105.

The generator is a lightweight possession-phase model, not a physics engine: each phase is a chain of
passes that ends in a shot, a turnover, a foul or an offside. Team ratings drawn from the seed tilt the
probabilities so different seeds give different stories.
"""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass, field

PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0
HALF_SECONDS = 45 * 60

FIRST_NAMES = [
    "Arda",
    "Kai",
    "Milo",
    "Noah",
    "Eren",
    "Luca",
    "Deniz",
    "Leon",
    "Alex",
    "Emir",
    "Theo",
    "Jude",
    "Owen",
    "Hugo",
    "Nico",
    "Adam",
    "Ivo",
    "Remy",
    "Tariq",
    "Mateo",
    "Sami",
    "Yusuf",
    "Elias",
    "Rafael",
    "Kofi",
    "Jonas",
    "Bruno",
    "Oskar",
    "Idris",
    "Tomas",
    "Aksel",
    "Cem",
    "Ilyas",
    "Malik",
    "Soren",
    "Dario",
    "Felix",
    "Anton",
    "Kerem",
    "Bilal",
]
LAST_NAMES = [
    "Vale",
    "Okafor",
    "Lindqvist",
    "Demirtas",
    "Moreau",
    "Castell",
    "Brandt",
    "Yilmazer",
    "Novak",
    "Sato",
    "Ferreira",
    "Kovac",
    "Haddad",
    "Reyes",
    "Larsen",
    "Mensah",
    "Aydinli",
    "Petrov",
    "Quinn",
    "Duval",
    "Ortega",
    "Holm",
    "Varga",
    "Keane",
    "Nakamura",
    "Sorensen",
    "Bakari",
    "Esposito",
    "Arslaner",
    "Wolfe",
    "Marin",
    "Celikel",
    "Rossetti",
    "Ekdahl",
    "Abara",
    "Lund",
    "Navarro",
    "Toivonen",
    "Kayali",
    "Brooks",
]

# Shirt number -> position for a 4-3-3 with five substitutes.
SQUAD_LAYOUT = [
    (1, "GK"),
    (2, "DF"),
    (3, "DF"),
    (4, "DF"),
    (5, "DF"),
    (6, "MF"),
    (8, "MF"),
    (10, "MF"),
    (7, "FW"),
    (9, "FW"),
    (11, "FW"),
    (12, "GK"),
    (13, "DF"),
    (14, "MF"),
    (15, "MF"),
    (16, "FW"),
]
STARTERS = 11


@dataclass(frozen=True)
class Player:
    id: str
    team: str
    number: int
    name: str
    position: str
    starter: bool

    @property
    def short_name(self) -> str:
        return self.name.split()[-1]


@dataclass(frozen=True)
class Team:
    id: str
    name: str
    short: str
    color: str
    attack: float
    defence: float
    tempo: float
    players: tuple[Player, ...]


@dataclass(frozen=True)
class MatchEvent:
    id: str
    period: int
    clock: float
    type: str
    team: str | None
    player: str | None
    x: float
    y: float
    possession: str | None
    phase: int
    end_x: float | None = None
    end_y: float | None = None
    target: str | None = None
    outcome: str | None = None
    detail: dict = field(default_factory=dict)

    @property
    def minute(self) -> int:
        return int(self.clock // 60) + 1

    @property
    def display_minute(self) -> str:
        regular_end = 45 if self.period == 1 else 90
        if self.minute > regular_end:
            return f"{regular_end}+{self.minute - regular_end}'"
        return f"{self.minute}'"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["minute"] = self.minute
        data["display_minute"] = self.display_minute
        return data


@dataclass(frozen=True)
class Match:
    seed: int
    venue: str
    teams: dict[str, Team]
    events: tuple[MatchEvent, ...]

    def player(self, player_id: str | None) -> Player | None:
        if player_id is None:
            return None
        team = self.teams["home" if player_id.startswith("H") else "away"]
        return next((p for p in team.players if p.id == player_id), None)

    def meta(self) -> dict:
        return {
            "seed": self.seed,
            "venue": self.venue,
            "synthetic": True,
            "teams": {
                key: {
                    "id": t.id,
                    "name": t.name,
                    "short": t.short,
                    "color": t.color,
                    "players": [asdict(p) for p in t.players],
                }
                for key, t in self.teams.items()
            },
            "event_count": len(self.events),
        }


def _other(team: str) -> str:
    return "away" if team == "home" else "home"


def _to_pitch(team: str, a: float, y: float) -> tuple[float, float]:
    """Convert attacking-normalised coordinates (a = distance from own goal line) to pitch coordinates."""
    x = a if team == "home" else PITCH_LENGTH - a
    return round(x, 1), round(y, 1)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _in_box(a: float, y: float) -> bool:
    return a > PITCH_LENGTH - 16.5 and 13.84 < y < 54.16


class _Simulator:
    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.seed = seed
        self.events: list[MatchEvent] = []
        self.phase = 0
        self.teams = self._build_teams()
        self.on_pitch = {key: {p.id for p in team.players if p.starter} for key, team in self.teams.items()}
        self.bench = {key: [p.id for p in team.players if not p.starter] for key, team in self.teams.items()}
        self.booked: set[str] = set()
        self.subs_due: list[tuple[float, str]] = []

    # --- squad -----------------------------------------------------------------------------------------
    def _build_teams(self) -> dict[str, Team]:
        # Surnames are unique within a match so commentary ("Vale scores!") is never ambiguous.
        squad_size = len(SQUAD_LAYOUT) * 2
        surnames = self.rng.sample(LAST_NAMES, squad_size)
        picked = [f"{self.rng.choice(FIRST_NAMES)} {last}" for last in surnames]
        specs = {
            "home": ("Northstar FC", "NOR", "#c5f665"),
            "away": ("Ember Athletic", "EMB", "#ed9e83"),
        }
        teams = {}
        for index, (key, (name, short, color)) in enumerate(specs.items()):
            prefix = "H" if key == "home" else "A"
            players = tuple(
                Player(
                    id=f"{prefix}{number}",
                    team=key,
                    number=number,
                    name=picked[index * len(SQUAD_LAYOUT) + i],
                    position=position,
                    starter=i < STARTERS,
                )
                for i, (number, position) in enumerate(SQUAD_LAYOUT)
            )
            teams[key] = Team(
                id=key,
                name=name,
                short=short,
                color=color,
                attack=round(self.rng.uniform(0.88, 1.12), 3),
                defence=round(self.rng.uniform(0.88, 1.12), 3),
                tempo=round(self.rng.uniform(0.85, 1.15), 3),
                players=players,
            )
        return teams

    def _pick(self, team: str, positions: dict[str, float], exclude: str | None = None) -> str:
        squad = [p for p in self.teams[team].players if p.id in self.on_pitch[team] and p.id != exclude]
        weights = [positions.get(p.position, 0.02) for p in squad]
        return self.rng.choices(squad, weights=weights)[0].id

    def _player_for_zone(self, team: str, a: float, exclude: str | None = None) -> str:
        if a < 25:
            weights = {"GK": 0.25, "DF": 0.6, "MF": 0.15}
        elif a < 45:
            weights = {"DF": 0.5, "MF": 0.45, "FW": 0.05}
        elif a < 75:
            weights = {"DF": 0.15, "MF": 0.6, "FW": 0.25}
        else:
            weights = {"DF": 0.05, "MF": 0.4, "FW": 0.55}
        return self._pick(team, weights, exclude)

    # --- events ----------------------------------------------------------------------------------------
    def _emit(
        self,
        period: int,
        clock: float,
        type_: str,
        team: str | None,
        player: str | None,
        a: float,
        y: float,
        possession: str | None,
        **extra,
    ) -> MatchEvent:
        x, py = _to_pitch(team or "home", a, y)
        if "end_a" in extra:
            end_x, end_y = _to_pitch(team or "home", extra.pop("end_a"), extra.pop("end_y"))
            extra["end_x"], extra["end_y"] = end_x, end_y
        event = MatchEvent(
            id=f"E{len(self.events) + 1:04d}",
            period=period,
            clock=round(clock, 1),
            type=type_,
            team=team,
            player=player,
            x=x,
            y=py,
            possession=possession,
            phase=self.phase,
            **extra,
        )
        self.events.append(event)
        return event

    def _run_due_subs(self, period: int, clock: float) -> None:
        while self.subs_due and self.subs_due[0][0] <= clock:
            _, team = self.subs_due.pop(0)
            outfield = [pid for pid in self.on_pitch[team] if self._position(team, pid) != "GK"]
            bench = [pid for pid in self.bench[team] if self._position(team, pid) != "GK"]
            if not outfield or not bench:
                continue
            off = self.rng.choice(sorted(outfield))
            same = [pid for pid in bench if self._position(team, pid) == self._position(team, off)]
            on = self.rng.choice(same or bench)
            self.on_pitch[team].discard(off)
            self.on_pitch[team].add(on)
            self.bench[team].remove(on)
            self._emit(
                period,
                clock,
                "substitution",
                team,
                on,
                52.5,
                1.0,
                None,
                target=off,
                detail={"off": off, "on": on},
            )

    def _index(self, team: str, pid: str) -> int:
        return next(i for i, p in enumerate(self.teams[team].players) if p.id == pid)

    def _position(self, team: str, pid: str) -> str:
        return self.teams[team].players[self._index(team, pid)].position

    def _shot(
        self,
        period: int,
        clock: float,
        team: str,
        shooter: str,
        a: float,
        y: float,
        assist: str | None,
        situation: str,
    ) -> tuple[float, str, float, float]:
        """Resolve a shot. Returns (clock, next possession, restart a, restart y)."""
        opp = _other(team)
        distance = math.hypot(PITCH_LENGTH - a, PITCH_WIDTH / 2 - y)
        angle = abs(math.atan2(abs(PITCH_WIDTH / 2 - y), max(PITCH_LENGTH - a, 0.5)))
        quality = 0.42 * math.exp(-(distance - 6) / 7.5) * (1 - angle / 2.2)
        if situation == "penalty":
            quality = 0.76
        quality *= self.teams[team].attack / self.teams[opp].defence
        quality = _clamp(quality, 0.01, 0.8)
        roll = self.rng.random()
        if roll < quality:
            outcome = "goal"
        elif roll < quality + 0.28:
            outcome = "saved"
        elif roll < quality + 0.28 + 0.2 and situation != "penalty":
            outcome = "blocked"
        else:
            outcome = "off_target"
        body = (
            "header"
            if situation == "corner"
            else self.rng.choices(["right_foot", "left_foot", "header"], [0.6, 0.3, 0.1])[0]
        )
        detail = {
            "distance_m": round(distance, 1),
            "chance_quality": round(quality, 2),
            "body_part": body,
            "situation": situation,
        }
        if assist:
            detail["assist"] = assist
        possession = team if outcome == "blocked" and self.rng.random() < 0.4 else opp
        keeper = self._pick(opp, {"GK": 1.0})
        if outcome == "saved":
            detail["goalkeeper"] = keeper
        self._emit(
            period,
            clock,
            "shot",
            team,
            shooter,
            a,
            y,
            possession,
            outcome=outcome,
            detail=detail,
            end_a=PITCH_LENGTH,
            end_y=round(_clamp(y + self.rng.gauss(0, 3), 28, 40), 1),
        )
        clock += self.rng.uniform(4, 9)
        if outcome == "goal":
            self._emit(
                period,
                clock,
                "goal",
                team,
                shooter,
                a,
                y,
                opp,
                target=assist,
                detail={"assist": assist, "situation": situation},
            )
            clock += self.rng.uniform(35, 60)
            return clock, opp, 52.5, 34.0
        if outcome in ("saved", "blocked") and self.rng.random() < 0.5:
            corner_y = self.rng.choice([0.5, 67.5])
            taker = self._pick(team, {"MF": 0.7, "FW": 0.2, "DF": 0.1})
            clock += self.rng.uniform(15, 30)
            self._emit(period, clock, "corner", team, taker, PITCH_LENGTH - 0.5, corner_y, team)
            if self.rng.random() < 0.32:
                header_by = self._pick(team, {"DF": 0.45, "FW": 0.45, "MF": 0.1})
                clock += self.rng.uniform(2, 4)
                return self._shot(
                    period,
                    clock,
                    team,
                    header_by,
                    self.rng.uniform(93, 100),
                    self.rng.uniform(27, 41),
                    taker,
                    "corner",
                )
            return clock + self.rng.uniform(3, 8), opp, 12.0, 34.0
        return clock + self.rng.uniform(10, 25), opp, 8.0, 34.0

    def _phase(self, period: int, clock: float, end: float, team: str, a: float, y: float) -> tuple:
        """Play one possession phase. Returns (clock, next possession, restart a, restart y)."""
        self.phase += 1
        opp = _other(team)
        holder = self._player_for_zone(team, a)
        last_passer: str | None = None
        attack, defence = self.teams[team].attack, self.teams[opp].defence
        for _ in range(18):
            if clock >= end:
                break
            clock += self.rng.uniform(2.2, 5.5) / self.teams[team].tempo
            final_third = a > 70
            if a > 76 and self.rng.random() < 0.095 * attack * (1.3 if _in_box(a, y) else 1.0):
                return self._shot(period, clock, team, holder, a, y, last_passer, "open_play")
            turnover_chance = (0.11 + (0.08 if final_third else 0.0)) * defence / attack
            if self.rng.random() < turnover_chance:
                return self._lose_ball(period, clock, team, holder, a, y)
            new_a = _clamp(a + self.rng.gauss(5.5 * self.teams[team].tempo, 9), 3, PITCH_LENGTH - 4)
            new_y = _clamp(y + self.rng.gauss(0, 13), 2, PITCH_WIDTH - 2)
            if new_a > 84 and self.rng.random() < 0.05:
                self._emit(
                    period,
                    clock,
                    "offside",
                    team,
                    self._player_for_zone(team, new_a, holder),
                    new_a,
                    new_y,
                    opp,
                )
                return clock + self.rng.uniform(8, 15), opp, PITCH_LENGTH - new_a, new_y
            receiver = self._player_for_zone(team, new_a, holder)
            self._emit(
                period,
                clock,
                "pass",
                team,
                holder,
                a,
                y,
                team,
                target=receiver,
                outcome="complete",
                end_a=round(new_a, 1),
                end_y=round(new_y, 1),
            )
            last_passer, holder, a, y = holder, receiver, new_a, new_y
        return clock, team, a, y

    def _lose_ball(self, period: int, clock: float, team: str, holder: str, a: float, y: float) -> tuple:
        opp = _other(team)
        opp_a = PITCH_LENGTH - a
        defender = self._player_for_zone(opp, opp_a)
        if self.rng.random() < 0.24:
            self._emit(period, clock, "foul", opp, defender, opp_a, y, team, target=holder)
            if _in_box(a, y) and self.rng.random() < 0.15:
                self._emit(period, clock + 2, "penalty_awarded", team, holder, a, y, team, target=defender)
                taker = self._pick(team, {"FW": 0.8, "MF": 0.2})
                return self._shot(period, clock + 70, team, taker, PITCH_LENGTH - 11, 34.0, None, "penalty")
            caution = 0.12 + (0.08 if a > 60 else 0)
            if self.rng.random() < (caution * 0.35 if defender in self.booked else caution):
                second = defender in self.booked
                self.booked.add(defender)
                card = "red_card" if second else "yellow_card"
                self._emit(
                    period, clock + 8, card, opp, defender, opp_a, y, team, detail={"second_yellow": second}
                )
                if second:
                    self.on_pitch[opp].discard(defender)
            clock += self.rng.uniform(12, 25)
            if a > 75 and self.rng.random() < 0.3:
                taker = self._pick(team, {"MF": 0.6, "FW": 0.4})
                self._emit(period, clock, "free_kick", team, taker, a, y, team)
                return self._shot(period, clock + 2, team, taker, a, y, None, "free_kick")
            return clock, team, a, y
        kind = "tackle" if self.rng.random() < 0.55 else "interception"
        self._emit(period, clock, kind, opp, defender, opp_a, y, opp, target=holder)
        return clock + self.rng.uniform(1, 3), opp, opp_a, y

    # --- match -----------------------------------------------------------------------------------------
    def run(self) -> Match:
        for team in ("home", "away"):
            times = sorted(self.rng.uniform(56 * 60, 84 * 60) for _ in range(3))
            self.subs_due.extend((t, team) for t in times)
        self.subs_due.sort()
        for period in (1, 2):
            start = 0.0 if period == 1 else float(HALF_SECONDS)
            regular_end = start + HALF_SECONDS
            stoppage = self.rng.randint(1, 4) if period == 1 else self.rng.randint(2, 6)
            end = regular_end + stoppage * 60
            team = "home" if period == 1 else "away"
            self.phase += 1
            self._emit(period, start, "kickoff", team, self._pick(team, {"FW": 1.0}), 52.5, 34.0, team)
            clock, a, y = start + 1, 52.5, 34.0
            announced = False
            while clock < end:
                if not announced and clock >= regular_end - 30:
                    self._emit(
                        period,
                        regular_end - 20,
                        "stoppage_time",
                        None,
                        None,
                        52.5,
                        34.0,
                        team,
                        detail={"minutes": stoppage},
                    )
                    announced = True
                if period == 2:
                    self._run_due_subs(period, clock)
                clock, team, a, y = self._phase(period, clock, end, team, a, y)
                if a == 52.5 and y == 34.0:  # restart after a goal
                    self._emit(
                        period, clock, "kickoff", team, self._pick(team, {"FW": 1.0}), 52.5, 34.0, team
                    )
            # The last phase may run a few seconds past the planned end; the whistle follows the last action.
            whistle = max([end - 1] + [e.clock + 1 for e in self.events if e.period == period])
            self._emit(
                period, whistle, "half_time" if period == 1 else "full_time", None, None, 52.5, 34.0, None
            )
        events = tuple(sorted(self.events, key=lambda e: (e.period, e.clock, int(e.id[1:]))))
        return Match(seed=self.seed, venue="Harbour Park (fictional)", teams=self.teams, events=events)


def generate_match(seed: int = 42) -> Match:
    """Generate a full, deterministic synthetic match for ``seed``."""
    if not isinstance(seed, int) or seed < 0 or seed > 2**32 - 1:
        raise ValueError("seed must be an integer between 0 and 2^32-1")
    return _Simulator(seed).run()
