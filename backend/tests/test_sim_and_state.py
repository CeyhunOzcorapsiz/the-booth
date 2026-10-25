from booth.facts import StatsDesk
from booth.sim import generate_match
from booth.state import MatchState


def test_generation_is_deterministic():
    a, b = generate_match(11), generate_match(11)
    assert [e.to_dict() for e in a.events] == [e.to_dict() for e in b.events]
    assert generate_match(12).events != a.events


def test_events_are_ordered_unique_and_on_the_pitch():
    match = generate_match(3)
    keys = [(e.period, e.clock) for e in match.events]
    assert keys == sorted(keys)
    assert len({e.id for e in match.events}) == len(match.events)
    for e in match.events:
        assert 0 <= e.x <= 105 and 0 <= e.y <= 68
    assert match.events[0].type == "kickoff"
    assert match.events[-1].type == "full_time"
    assert sum(e.type == "half_time" for e in match.events) == 1


def test_realistic_averages_over_many_seeds():
    goals = shots = 0
    for seed in range(30):
        events = generate_match(seed).events
        goals += sum(e.type == "goal" for e in events)
        shots += sum(e.type == "shot" for e in events)
    assert 1.5 < goals / 30 < 4.0
    assert 18 < shots / 30 < 40


def test_state_tracks_score_and_possession():
    match = generate_match(5)
    state = MatchState(match)
    for event in match.events:
        state.apply(event)
    goals = {"home": 0, "away": 0}
    for e in match.events:
        if e.type == "goal":
            goals[e.team] += 1
    assert state.score == goals
    pct = state.possession_pct()
    assert pct["home"] + pct["away"] == 100
    assert -1 <= state.momentum() <= 1


def test_frozen_state_does_not_change_later():
    match = generate_match(5)
    state = MatchState(match)
    for event in match.events[:200]:
        state.apply(event)
    frozen = state.freeze()
    before = frozen.snapshot["teams"]["home"]["passes"]
    for event in match.events[200:400]:
        state.apply(event)
    assert frozen.snapshot["teams"]["home"]["passes"] == before


def test_stats_desk_registers_facts_and_exposes_tools():
    match = generate_match(5)
    state = MatchState(match)
    for event in match.events[:500]:
        state.apply(event)
    desk = StatsDesk(state.freeze())
    desk.score()
    desk.team_stats("Northstar FC")
    desk.player_stats("H9")
    assert "F-score" in desk.sheet.facts
    assert "F-home-shots" in desk.sheet.facts
    tools = desk.as_tools()
    assert {t.name for t in tools} >= {"score", "team_stats", "player_stats", "compare", "momentum"}
