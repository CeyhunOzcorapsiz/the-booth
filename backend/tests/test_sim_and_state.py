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


def test_surnames_are_unique_within_a_match():
    for seed in range(20):
        match = generate_match(seed)
        surnames = [p.short_name for t in match.teams.values() for p in t.players]
        assert len(surnames) == len(set(surnames))


def test_storyline_agent_spots_the_seed_119_comeback():
    match = generate_match(119)
    state = MatchState(match)
    for event in match.events:
        state.apply(event)
    kinds = [s.kind for s in state.story.storylines]
    assert {"comeback", "quick_fire", "late_winner", "brace"} <= set(kinds)
    assert "turnaround" not in kinds  # folded into the late winner
    comeback = next(s for s in state.story.storylines if s.kind == "comeback")
    assert comeback.team == "home" and comeback.numbers[0] == 2
    assert state.snapshot()["storylines"]


def test_on_pitch_lineups_follow_substitutions_and_red_cards():
    for seed in range(40):
        match = generate_match(seed)
        state = MatchState(match)
        for event in match.events:
            state.apply(event)
        reds = {"home": 0, "away": 0}
        for e in match.events:
            if e.type == "red_card":
                reds[e.team] += 1
        for team in ("home", "away"):
            lineup = [pid for pid in state.on_pitch[team] if pid]
            assert len(state.on_pitch[team]) == 11
            assert len(lineup) == 11 - reds[team]
            assert len(set(lineup)) == len(lineup)


def test_dataset_export_writes_joinable_tables(tmp_path):
    import csv

    from booth.dataset import export

    counts = export(119, 2, tmp_path)
    assert counts["matches"] == 2 and counts["events"] > 1500 and counts["players"] == 64
    matches = list(csv.DictReader(open(tmp_path / "matches.csv", encoding="utf-8")))
    assert matches[0]["match_id"] == "M000119"
    assert matches[0]["home_goals"] == "3" and "late_winner" in matches[0]["storylines"]
    events = list(csv.DictReader(open(tmp_path / "events.csv", encoding="utf-8")))
    assert {e["match_id"] for e in events} == {"M000119", "M000120"}
    assert sum(1 for _ in open(tmp_path / "events.jsonl", encoding="utf-8")) == len(events)


def test_pass_quality_and_speed_metrics():
    match = generate_match(119)
    passes = [e for e in match.events if e.type == "pass"]
    assert {"complete", "intercepted"} == {e.outcome for e in passes}
    for e in passes:
        assert 5 <= e.detail["difficulty"] <= 99 and 25 <= e.detail["ball_speed_kmh"] <= 105
    shots = [e for e in match.events if e.type == "shot"]
    assert all(40 <= s.detail["ball_speed_kmh"] <= 130 for s in shots)
    long_forward = max(passes, key=lambda e: e.detail["pass_distance_m"] + e.detail["progressive_m"])
    short_back = min(passes, key=lambda e: e.detail["pass_distance_m"] + e.detail["progressive_m"])
    assert long_forward.detail["difficulty"] > short_back.detail["difficulty"]
    state = MatchState(match)
    for event in match.events:
        state.apply(event)
    line = state.team_line("home")
    assert 80 <= line["pass_accuracy_pct"] <= 98
    assert line["fastest_shot_kmh"] == max(s.detail["ball_speed_kmh"] for s in shots if s.team == "home")
    desk = StatsDesk(state.freeze())
    assert desk.pass_quality("home")["pass_accuracy_pct"]["value"] == line["pass_accuracy_pct"]


def test_enrichment_keeps_the_seeded_story():
    goals = [(e.display_minute, e.team) for e in generate_match(119).events if e.type == "goal"]
    assert goals == [("20'", "away"), ("60'", "away"), ("78'", "home"), ("82'", "home"), ("90'", "home")]
