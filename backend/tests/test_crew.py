import asyncio
from collections import Counter

import pytest

from booth.agents.base import Job
from booth.agents.fact_checker import FactChecker
from booth.crew import Crew
from booth.facts import FactSheet, StatsDesk
from booth.llm import LLMConfig, LLMRuntime, LLMUnavailable
from booth.orchestrator import Broadcast
from booth.profile import ViewerProfile
from booth.sim import generate_match
from booth.state import MatchState


class ScriptedRuntime(LLMRuntime):
    """Stands in for a model: returns scripted replies per agent, or raises."""

    def __init__(self, replies: dict[str, list]):
        super().__init__(
            LLMConfig(provider="test", model="fake", api_key="x", min_importance=0.0), client=object()
        )
        self.replies = {k: list(v) for k, v in replies.items()}
        self.calls_by_agent: Counter = Counter()

    async def run(self, name, instructions, prompt, tools=None):
        self.calls_by_agent[name] += 1
        queue = self.replies.get(name) or [LLMUnavailable("no script")]
        reply = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(reply, Exception):
            raise reply
        return reply(prompt) if callable(reply) else reply


def goal_job(seed: int = 1) -> Job:
    match = generate_match(seed)
    state = MatchState(match)
    for event in match.events:
        state.apply(event)
        if event.type == "goal":
            return Job("J1", event, ("pbp", "color"), 1.0, state.freeze())
    pytest.skip("seed has no goal")


def collect_trace():
    log = []
    return log, lambda agent, status, detail, ms: log.append((agent, status, detail))


def test_fact_checker_rejects_invented_numbers_and_players():
    job = goal_job()
    sheet = FactSheet()
    StatsDesk(job.state, sheet).team_stats(job.event.team)
    checker = FactChecker()
    assert not checker.check(
        "What a strike, his 417th career goal!", "pbp", job.event, job.state, sheet
    ).approved
    match = job.state.match
    bystander = next(
        p
        for t in match.teams.values()
        for p in t.players
        if p.id not in (job.event.player, job.event.target)
        and p.short_name != match.player(job.event.player).short_name
    )
    verdict = checker.check(f"Great work by {bystander.short_name}.", "pbp", job.event, job.state, sheet)
    assert not verdict.approved
    shots = job.state.snapshot["teams"][job.event.team]["shots"]
    assert checker.check(f"That's {shots} shots now.", "color", job.event, job.state, sheet).approved


async def test_offline_crew_produces_verified_template_segments():
    log, trace = collect_trace()
    segments = await Crew(None).produce(goal_job(), ViewerProfile("en", "hype"), trace)
    assert [s.kind for s in segments] == ["pbp", "color"]
    assert all(s.source == "template" and s.text for s in segments)
    assert any(agent == "stats-producer" for agent, *_ in log)


async def test_rejected_draft_is_handed_back_once_then_approved():
    job = goal_job()
    scorer = job.state.match.player(job.event.player).short_name
    runtime = ScriptedRuntime(
        {
            "pbp": ["It's 999 goals for the club!", f"Goal! {scorer} finishes it off."],
            "color": ["Clinical finish."],
            "stats_producer": [LLMUnavailable("quota")],
            "fact_checker": ['{"approved": true, "reason": "ok"}'],
        }
    )
    log, trace = collect_trace()
    segments = await Crew(runtime).produce(job, ViewerProfile("en", "hype"), trace)
    pbp = segments[0]
    assert pbp.source == "ai" and scorer in pbp.text
    assert runtime.calls_by_agent["pbp"] == 2
    statuses = [(a, s) for a, s, _ in log]
    assert ("fact-checker", "rejected") in statuses and ("fact-checker", "approved") in statuses


async def test_failures_fall_back_to_templates_and_bad_translations_are_refused():
    job = goal_job()
    runtime = ScriptedRuntime(
        {
            "pbp": ["Goal for the visitors in minute 12345."],  # rejected twice -> template
            "color": [LLMUnavailable("timeout")],
            "stats_producer": [LLMUnavailable("timeout")],
        }
    )
    log, trace = collect_trace()
    segments = await Crew(runtime).produce(job, ViewerProfile("tr", "calm"), trace)
    assert all(s.source == "template" for s in segments)
    assert segments[0].lang == "tr"

    runtime = ScriptedRuntime(
        {
            "pbp": ["Goal!"],
            "localizer": ["Gol! 7"],
            "color": [LLMUnavailable("x")],
            "stats_producer": [LLMUnavailable("x")],
        }
    )
    segments = await Crew(runtime).produce(job, ViewerProfile("de", "hype"), trace)
    assert segments[0].source == "template"  # translation added a number, so it was refused


async def test_circuit_breaker_opens_after_repeated_failures():
    runtime = LLMRuntime(
        LLMConfig(provider="test", model="m", api_key="k", breaker_threshold=2), client=object()
    )
    runtime._record_failure("a", RuntimeError())
    assert runtime.available()
    runtime._record_failure("a", RuntimeError())
    assert not runtime.available()


async def test_cache_shares_segments_between_viewers_with_same_profile():
    crew = Crew(None)
    job = goal_job()
    _, trace = collect_trace()
    first = await crew.produce(job, ViewerProfile("en", "hype"), trace)
    log, trace = collect_trace()
    second = await crew.produce(job, ViewerProfile("en", "hype"), trace)
    assert [s.text for s in first] == [s.text for s in second]
    assert log[0][1] == "cache"


@pytest.mark.parametrize(
    "profile",
    [
        ViewerProfile("en", "hype"),
        ViewerProfile("tr", "beginner", accessible=True),
        ViewerProfile("en", "tactical", follow="H9"),
        ViewerProfile("tr", "calm"),
    ],
)
async def test_full_offline_broadcast_passes_its_own_fact_checks(profile):
    show = Broadcast(generate_match(21), profile, Crew(None), speed=1e9, max_gap_s=0)
    kinds: Counter = Counter()
    async for message in show.stream():
        assert message["type"] != "error", message
        if message["type"] == "segment":
            kinds[message["kind"]] += 1
            assert message["text"]
            assert not any(n.startswith("template check") for n in message["notes"]), message
    assert kinds["recap"] == 2
    assert kinds["pbp"] > 30


async def test_start_minute_skips_ahead():
    show = Broadcast(generate_match(21), ViewerProfile(), Crew(None), speed=1e9, max_gap_s=0, start_minute=80)
    first_event = None
    async for message in show.stream():
        if message["type"] == "event":
            first_event = message["event"]
            break
    assert first_event["clock"] >= 80 * 60


def test_runtime_reports_offline_without_config():
    status = LLMRuntime(LLMConfig()).status()
    assert status["provider"] == "offline" and not status["configured"]
    with pytest.raises(LLMUnavailable):
        asyncio.run(LLMRuntime(LLMConfig()).run("x", "y", "z"))


async def test_evaluation_reports_offline_baseline():
    from booth.evaluate import evaluate, parse_profile, to_markdown

    runtime = LLMRuntime(LLMConfig())
    reports = await evaluate(119, [parse_profile("tr:beginner:accessible")], runtime)
    data = reports[0].to_dict()
    assert data["fact_check_pass_rate"] == 1.0
    assert data["sources"] == {"template": sum(data["segments"].values())}
    assert "seed 119" in to_markdown(119, runtime, reports)


async def test_new_storyline_reaches_the_analyst_and_trace():
    from booth.moment import PRESETS, compare, highlights

    match = generate_match(119)
    winner = [h for h in highlights(match) if h["type"] == "goal"][-1]["event_id"]
    result = await compare(match, winner, [PRESETS[0]], Crew(None))
    broadcast = result["broadcasts"][0]
    color = next(s for s in broadcast["segments"] if s["kind"] == "color")
    assert "late winner" in color["text"].lower()
    assert any(e["id"].endswith("story-late_winner") for e in color["evidence"])
    assert any(t["agent"] == "storyline" for t in broadcast["trace"])
