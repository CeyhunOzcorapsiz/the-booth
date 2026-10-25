import math
import statistics

import pytest

from booth.facts import StatsDesk
from booth.overlays import build_cues
from booth.sim import generate_match
from booth.sim.tracking import SPRINT_KMH, build_tracking, tracking_for
from booth.state import MatchState


@pytest.mark.parametrize("seed", [3, 42, 119])
def test_tracking_looks_like_football(seed):
    match = generate_match(seed)
    tracking = build_tracking(match)
    outfield = [
        tracking.stats_until(p.id, 2, 1e9)
        for team in match.teams.values()
        for p in team.players
        if p.starter and p.position != "GK"
    ]
    assert 9.0 <= statistics.mean(s["distance_km"] for s in outfield) <= 12.5
    assert all(s["top_speed_kmh"] <= 36 for s in outfield)
    assert max(s["top_speed_kmh"] for s in outfield) >= SPRINT_KMH
    assert 10 <= statistics.mean(s["sprints"] for s in outfield) <= 45
    keeper = tracking.stats_until("H1", 2, 1e9)
    assert 3.5 <= keeper["distance_km"] <= 7.5


def test_players_are_near_their_events_and_on_the_pitch():
    match = generate_match(119)
    tracking = tracking_for(match)
    gaps = []
    for event in match.events:
        if event.player and event.type in ("pass", "shot", "tackle", "interception"):
            x, y = tracking.position(event.player, event.period, event.clock)
            assert 0 <= x <= 105 and 0 <= y <= 68
            gaps.append(math.hypot(x - event.x, y - event.y))
    assert statistics.median(gaps) < 3.0


def test_substitutes_only_appear_once_they_come_on():
    match = generate_match(119)
    tracking = tracking_for(match)
    sub = next(e for e in match.events if e.type == "substitution")
    on, off = sub.detail["on"], sub.detail["off"]
    assert tracking.position(on, 1, 600) is None and tracking.position(off, 1, 600) is not None
    assert tracking.position(on, sub.period, sub.clock + 60) is not None
    assert tracking.position(off, sub.period, sub.clock + 60) is None


def test_state_desk_and_overlays_use_tracking():
    match = generate_match(119)
    state = MatchState(match)
    for event in match.events:
        state.apply(event)
    snap = state.snapshot()
    assert len(snap["positions"]) == 22
    assert 90 <= snap["teams"]["home"]["distance_km"] <= 130
    desk = StatsDesk(state.freeze())
    physical = desk.physical("home")
    assert physical["top_runners"] and "F-home-distance_km" in desk.sheet.facts
    assert "distance_km" in desk.player_stats("H9")
    cues = build_cues(match)
    assert any(c["type"] == "player_tag" and c["payload"]["metric"] == "running_speed_kmh" for c in cues)
    assert any(
        r["label"] == "Distance (km)" for c in cues if c["type"] == "stat_card" for r in c["payload"]["rows"]
    )
