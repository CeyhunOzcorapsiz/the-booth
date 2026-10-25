"""Synthetic player tracking: where all 22 players are, second by second.

The match generator produces event data (who did what, where). A tracking provider would add continuous
positions for every player. This module synthesises them, consistently with the events:

1. **Keyframes** at every event: players involved in the event are placed where it happened; everyone else
   takes their slot in a 4-3-3 that shifts with the ball and with who has possession.
2. **Physics**: between keyframes players move at most at sprint speed, so an actor who starts far from the
   ball arrives late rather than teleporting.
3. **Off-ball movement**: smooth, deterministic per-player drift (checking runs, jockeying) on top.

Sampled at 1 Hz, the result is calibrated to look like football: about 10-12 km per outfield player per
match, top speeds of 29-34 km/h and roughly 15-40 sprints (two seconds or more above 25 km/h) per player. It is synthetic data, not a model of
real players, and everything is deterministic from the match seed.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass, field
from functools import lru_cache

from booth.sim.match import PITCH_LENGTH, PITCH_WIDTH, Match, generate_match

HZ = 1.0
MAX_SPEED = 9.4  # m/s (~34 km/h)
SPRINT_KMH = 25.0
HIGH_INTENSITY_KMH = 19.8
# Slot order matches MatchState lineups: shirts 1, 2, 3, 4, 5, 6, 8, 10, 7, 9, 11 (home attacking right).
SHAPE = [
    (5, 34),
    (32, 58),
    (32, 10),
    (29, 26),
    (29, 42),
    (43, 34),
    (51, 50),
    (53, 18),
    (66, 58),
    (70, 34),
    (66, 10),
]
DRIFT_M = 5.8
SPRINT_MIN_S = 2  # a sprint is at least two consecutive seconds above SPRINT_KMH


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def slot_position(team: str, slot: int, ball_x: float, ball_y: float, attacking: bool) -> tuple[float, float]:
    """Where a player in ``slot`` stands given the ball and possession (same model the old UI used)."""
    fx, fy = SHAPE[slot]
    flip = team == "away"
    a = PITCH_LENGTH - ball_x if flip else ball_x
    by = PITCH_WIDTH - ball_y if flip else ball_y
    if slot == 0:
        x = fx + (a - 52.5) * 0.06
        y = 34 + (by - 34) * 0.15
    else:
        x = fx + (a - 52.5) * 0.55 + (5 if attacking else -4)
        y = 34 + (fy - 34) * (1.05 if attacking else 0.8) + (by - 34) * 0.3
    x, y = _clamp(x, 2, PITCH_LENGTH - 2), _clamp(y, 2, PITCH_WIDTH - 2)
    return (PITCH_LENGTH - x, PITCH_WIDTH - y) if flip else (x, y)


def _drift(pid: str, t: float, slot: int) -> tuple[float, float]:
    """Smooth, deterministic off-ball movement in metres."""
    seed = sum(ord(c) * (i + 1) for i, c in enumerate(pid))
    amp = DRIFT_M * (0.7 if slot == 0 else 1.0)
    p1, p2, p3 = seed % 97 / 15.4, seed % 89 / 14.2, seed % 83 / 13.2
    dx = amp * (0.6 * math.sin(t * 0.21 + p1) + 0.4 * math.sin(t * 0.47 + p2))
    dy = amp * (0.6 * math.sin(t * 0.17 + p3) + 0.4 * math.sin(t * 0.39 + p1 + p2))
    return dx, dy


@dataclass
class PlayerTrack:
    """1 Hz samples for one player: times (absolute seconds), positions, cumulative distance, speeds."""

    times: list[float] = field(default_factory=list)
    xy: list[tuple[float, float]] = field(default_factory=list)
    distance: list[float] = field(default_factory=list)  # cumulative metres
    speed: list[float] = field(default_factory=list)  # km/h over the previous second
    sprints: list[int] = field(default_factory=list)  # cumulative sprint count
    high_intensity: list[float] = field(default_factory=list)  # cumulative metres above 19.8 km/h
    top_speed: list[float] = field(default_factory=list)  # running maximum km/h

    def index_at(self, t: float) -> int:
        return bisect_right(self.times, t) - 1

    def finish(self) -> None:
        """Precompute running totals so any match position is an O(log n) lookup."""
        sprints, run, high, top = 0, 0, 0.0, 0.0
        for j, s in enumerate(self.speed):
            run = run + 1 if s >= SPRINT_KMH else 0
            if run == SPRINT_MIN_S:
                sprints += 1
            if s >= HIGH_INTENSITY_KMH and j:
                high += self.distance[j] - self.distance[j - 1]
            top = max(top, s)
            self.sprints.append(sprints)
            self.high_intensity.append(high)
            self.top_speed.append(top)


def absolute(period: int, clock: float) -> float:
    """A single increasing timeline: second-half clocks restart at 45:00, so they are offset."""
    return clock + (10_000.0 if period == 2 else 0.0)


@dataclass
class Tracking:
    match: Match
    players: dict[str, PlayerTrack]

    def position(self, pid: str, period: int, clock: float) -> tuple[float, float] | None:
        track = self.players.get(pid)
        if not track or not track.times:
            return None
        t = absolute(period, clock)
        i = track.index_at(t)
        if i < 0 or t - track.times[i] > 2.5:
            return None  # not on the pitch at that moment
        if i + 1 < len(track.times) and track.times[i + 1] - track.times[i] <= 1.5:
            u = (t - track.times[i]) / (track.times[i + 1] - track.times[i])
            (x0, y0), (x1, y1) = track.xy[i], track.xy[i + 1]
            return x0 + (x1 - x0) * u, y0 + (y1 - y0) * u
        return track.xy[i]

    def positions(self, period: int, clock: float) -> dict[str, tuple[float, float]]:
        out = {}
        for pid in self.players:
            pos = self.position(pid, period, clock)
            if pos:
                out[pid] = (round(pos[0], 1), round(pos[1], 1))
        return out

    def stats_until(self, pid: str, period: int, clock: float) -> dict:
        """Physical stats for a player from kick-off up to a match position."""
        track = self.players.get(pid)
        if not track or not track.times:
            return {"distance_km": 0.0, "top_speed_kmh": 0.0, "sprints": 0, "high_intensity_m": 0}
        i = track.index_at(absolute(period, clock))
        if i < 0:
            return {"distance_km": 0.0, "top_speed_kmh": 0.0, "sprints": 0, "high_intensity_m": 0}
        return {
            "distance_km": round(track.distance[i] / 1000, 2),
            "top_speed_kmh": round(track.top_speed[i], 1),
            "sprints": track.sprints[i],
            "high_intensity_m": int(track.high_intensity[i]),
        }

    def speed_at(self, pid: str, period: int, clock: float) -> float:
        track = self.players.get(pid)
        if not track or not track.times:
            return 0.0
        i = track.index_at(absolute(period, clock))
        return round(track.speed[i], 1) if i >= 0 else 0.0


def _keyframes(match: Match) -> dict[str, list[tuple[float, float, float, int, bool]]]:
    """(absolute time, x, y, slot, pinned) per player at every event, with lineup changes applied."""
    lineups = {key: [p.id for p in team.players if p.starter] for key, team in match.teams.items()}
    possession = "home"
    frames: dict[str, list] = {p.id: [] for team in match.teams.values() for p in team.players}
    for event in match.events:
        t = absolute(event.period, event.clock)
        if event.type == "substitution" and event.team:
            lineup = lineups[event.team]
            off, on = event.detail.get("off"), event.detail.get("on")
            if off in lineup:
                lineup[lineup.index(off)] = on
        if event.type == "red_card" and event.team and event.player in lineups[event.team]:
            lineups[event.team][lineups[event.team].index(event.player)] = None
        if event.possession:
            possession = event.possession
        ball_x = event.end_x if event.end_x is not None else event.x
        ball_y = event.end_y if event.end_y is not None else event.y
        pinned = {}
        if event.type not in ("substitution", "half_time", "full_time", "stoppage_time"):
            if event.player:
                pinned[event.player] = (event.x, event.y)
            if event.target and event.end_x is not None and event.type == "pass":
                pinned[event.target] = (event.end_x, event.end_y)
        for team, lineup in lineups.items():
            for slot, pid in enumerate(lineup):
                if pid is None:
                    continue
                x, y = pinned.get(pid) or slot_position(team, slot, ball_x, ball_y, possession == team)
                frames[pid].append((t, x, y, slot, pid in pinned))
        if event.type in ("half_time", "full_time"):
            for pid in frames:
                if frames[pid] and frames[pid][-1][0] == t:
                    frames[pid].append((t + 0.001, *frames[pid][-1][1:3], -1, False))  # marks the break
    return frames


def _top_speed(pid: str, slot: int) -> float:
    """Each player's own top speed in m/s (about 29-34 km/h; goalkeepers slower)."""
    seed = sum(ord(c) * (i + 3) for i, c in enumerate(pid))
    kmh = 29.0 + (seed % 53) / 52 * 5.0
    return (kmh - 6.0 if slot == 0 else kmh) / 3.6


def _sample(pid: str, keys: list[tuple[float, float, float, int, bool]]) -> PlayerTrack:
    """Move the player between keyframes with a speed and acceleration limit, plus off-ball drift."""
    track = PlayerTrack()
    if not keys:
        return track
    slot0 = max(keys[0][3], 0)
    vmax = _top_speed(pid, slot0)
    accel = 2.3  # m/s per second
    x, y = keys[0][1], keys[0][2]
    vx = vy = 0.0
    total = 0.0
    k = 0
    t = keys[0][0]
    end = keys[-1][0]
    last = None
    while t <= end:
        while k + 1 < len(keys) and keys[k + 1][0] <= t:
            k += 1
        if keys[k][3] == -1:  # half-time break: resume at the next keyframe, no distance counted
            if k + 1 >= len(keys):
                break
            k += 1
            t, x, y = keys[k][0], keys[k][1], keys[k][2]
            vx = vy = 0.0
            last = None
        nxt = keys[k + 1] if k + 1 < len(keys) else keys[k]
        remaining = max(nxt[0] - t, 1 / HZ)
        gap = math.hypot(nxt[1] - x, nxt[2] - y)
        want = min(gap / remaining, vmax)  # arrive on time if possible, never faster than top speed
        heading = math.atan2(nxt[2] - y, nxt[1] - x)
        dvx, dvy = math.cos(heading) * want - vx, math.sin(heading) * want - vy
        dv = math.hypot(dvx, dvy)
        if dv > accel / HZ:
            dvx, dvy = dvx * accel / HZ / dv, dvy * accel / HZ / dv
        vx, vy = vx + dvx, vy + dvy
        x, y = x + vx / HZ, y + vy / HZ
        drift = _drift(pid, t, max(keys[k][3], 0))
        # fade the drift out when the player is about to be (or just was) on the ball
        near = min(remaining if nxt[4] else 9.0, (t - keys[k][0]) if keys[k][4] else 9.0)
        fade = _clamp(near / 3.0, 0.0, 1.0)
        px = _clamp(x + drift[0] * fade, 0.5, PITCH_LENGTH - 0.5)
        py = _clamp(y + drift[1] * fade, 0.5, PITCH_WIDTH - 0.5)
        if last is not None:
            moved = math.hypot(px - last[0], py - last[1])
            speed = min(moved * HZ, vmax * 1.04) * 3.6
            total += moved
        else:
            speed = 0.0
        last = (px, py)
        track.times.append(t)
        track.xy.append((px, py))
        track.distance.append(total)
        track.speed.append(speed)
        t += 1 / HZ
    track.finish()
    return track


def build_tracking(match: Match) -> Tracking:
    frames = _keyframes(match)
    return Tracking(match=match, players={pid: _sample(pid, keys) for pid, keys in frames.items()})


@lru_cache(maxsize=16)
def tracking_for_seed(seed: int) -> Tracking:
    return build_tracking(generate_match(seed))


def tracking_for(match: Match) -> Tracking:
    """Tracking for a generated match (cached by seed; matches are deterministic per seed)."""
    return tracking_for_seed(match.seed)
