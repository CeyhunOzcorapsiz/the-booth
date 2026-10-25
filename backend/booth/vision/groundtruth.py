"""Ground truth for a video clip: where the ball and every player are at each frame, and the events.

The ball is carried by the player in possession and travels between players at the pass or shot speed
recorded on the event. Everything is derived from the synthetic match and tracking, so the auto-eventing
pipeline can be scored against exactly what was rendered.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from booth.sim.match import Match, MatchEvent
from booth.sim.tracking import Tracking, absolute

FPS = 10
CARRY_OFFSET_M = 0.7


@dataclass(frozen=True)
class Frame:
    t: float  # absolute seconds (see tracking.absolute)
    period: int
    clock: float
    ball: tuple[float, float]
    players: dict[str, tuple[float, float]]


@dataclass(frozen=True)
class TruthEvent:
    kind: str  # pass | turnover | shot
    t: float  # absolute time the ball left the player
    team: str
    player: str
    end_t: float
    distance_m: float
    speed_kmh: float
    source: str  # event id


def _flight(event: MatchEvent, start: tuple[float, float], end: tuple[float, float]) -> float:
    speed = max(event.detail.get("ball_speed_kmh", 60) / 3.6, 5.0)
    return max(math.dist(start, end) / speed, 0.2)


def _possession_changes(segments: list, events: list[MatchEvent]) -> list[TruthEvent]:
    """Every time the ball passes from one team's carrier to the other's (tackles, interceptions, saves,
    restarts), as seen on video. Restarts after a goal are skipped: the ball is placed on the spot."""
    goals = [absolute(e.period, e.clock) for e in events if e.type == "goal"]
    changes = []
    previous = None  # (carrier, end time of the carry)
    for seg_t0, seg_t1, kind, data in segments:
        if kind != "carry":
            continue
        if previous and previous[0][:1] != data[:1]:
            if not any(previous[1] - 1 <= g <= seg_t0 + 1 for g in goals):
                team = "home" if data.startswith("H") else "away"
                changes.append(
                    TruthEvent("turnover", previous[1], team, data, seg_t0, 0.0, 0.0, "possession")
                )
        previous = (data, seg_t1)
    return changes


def build(match: Match, tracking: Tracking, period: int, start_clock: float, end_clock: float):
    """Frames at FPS and the truth events between two clock times of one half."""
    events = [e for e in match.events if e.period == period and start_clock - 30 <= e.clock <= end_clock]
    t0, t1 = absolute(period, start_clock), absolute(period, end_clock)

    # ball segments: (t_start, t_end, kind, data); kind 'carry' (holder id) or 'flight' (start, end)
    segments: list[tuple[float, float, str, object]] = []
    truth: list[TruthEvent] = []
    holder: str | None = None
    for i, event in enumerate(events):
        t = absolute(event.period, event.clock)
        nxt = absolute(events[i + 1].period, events[i + 1].clock) if i + 1 < len(events) else t1 + 1
        here = tracking.position(event.player, event.period, event.clock) if event.player else None
        if event.type in ("pass", "shot") and here:
            if event.type == "pass" and event.outcome == "complete" and event.target:
                arrive = tracking.position(event.target, event.period, event.clock + 1.0)
                end = arrive or (event.end_x, event.end_y)
                receiver = event.target
            else:  # intercepted pass or shot
                end = (event.end_x, event.end_y)
                receiver = None
            flight = min(_flight(event, here, end), max(nxt - t, 0.2))
            segments.append((t, t + flight, "flight", (here, end)))
            kind = "shot" if event.type == "shot" else ("pass" if event.outcome == "complete" else None)
            if kind:
                truth.append(
                    TruthEvent(
                        kind,
                        t,
                        event.team,
                        event.player,
                        t + flight,
                        round(math.dist(here, end), 1),
                        round(math.dist(here, end) / flight * 3.6, 1),
                        event.id,
                    )
                )
            holder = receiver
            if receiver:
                segments.append((t + flight, nxt, "carry", receiver))
            continue
        if event.type in ("tackle", "interception") and event.player:
            holder = event.player
        elif event.type in ("kickoff", "corner", "free_kick") and event.player:
            holder = event.player
        elif event.type == "goal":
            holder = None
        if holder:
            segments.append((t, nxt, "carry", holder))
        else:
            spot = (event.end_x, event.end_y) if event.end_x is not None else (event.x, event.y)
            segments.append((t, nxt, "rest", spot))

    truth += _possession_changes(segments, events)

    frames: list[Frame] = []
    k = 0
    n = int((t1 - t0) * FPS)
    last_ball = (52.5, 34.0)
    for f in range(n):
        t = t0 + f / FPS
        clock = t - (10_000.0 if period == 2 else 0.0)
        players = tracking.positions(period, clock)
        while k + 1 < len(segments) and segments[k + 1][0] <= t:
            k += 1
        ball = last_ball
        if segments and segments[k][0] <= t:
            seg_t0, seg_t1, kind, data = segments[k]
            if kind == "flight" and t <= seg_t1:
                (sx, sy), (ex, ey) = data
                u = (t - seg_t0) / max(seg_t1 - seg_t0, 1e-6)
                ball = (sx + (ex - sx) * u, sy + (ey - sy) * u)
            elif kind == "flight":
                ball = data[1]
            elif kind == "carry" and data in players:
                px, py = players[data]
                attack = 1 if data.startswith("H") else -1
                ball = (px + CARRY_OFFSET_M * attack, py + 0.3)
            elif kind == "rest":
                ball = data
        last_ball = ball
        frames.append(Frame(t, period, clock, (round(ball[0], 2), round(ball[1], 2)), players))
    truth = [e for e in truth if t0 <= e.t <= t1 - 0.5]
    return frames, truth
