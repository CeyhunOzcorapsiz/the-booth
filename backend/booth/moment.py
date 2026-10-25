"""Same moment, different broadcasts: run several viewer profiles over one event side by side."""

from __future__ import annotations

from booth.agents.director import Director
from booth.crew import Crew
from booth.profile import ViewerProfile
from booth.sim.match import Match, MatchEvent
from booth.state import MatchState

PRESETS = (
    ViewerProfile("en", "hype"),
    ViewerProfile("tr", "beginner", accessible=True),
    ViewerProfile("en", "tactical"),
)
MAX_PROFILES = 4
HIGHLIGHT_TYPES = {"goal", "red_card", "penalty_awarded"}


def highlights(match: Match) -> list[dict]:
    """Moments worth comparing: goals, red cards, penalties and big saves."""
    out = []
    for event in match.events:
        big_save = (
            event.type == "shot" and event.outcome == "saved" and event.detail.get("chance_quality", 0) > 0.25
        )
        if event.type in HIGHLIGHT_TYPES or big_save:
            player = match.player(event.player)
            label = "big save" if big_save else event.type.replace("_", " ")
            out.append(
                {
                    "event_id": event.id,
                    "minute": event.display_minute,
                    "type": event.type,
                    "team": event.team,
                    "label": f"{event.display_minute} {label} · {player.name if player else ''}".strip(" ·"),
                }
            )
    return out


def _state_through(match: Match, event_id: str) -> tuple[MatchState, MatchEvent]:
    state = MatchState(match)
    for event in match.events:
        state.apply(event)
        if event.id == event_id:
            return state, event
    raise KeyError(event_id)


async def compare(match: Match, event_id: str, profiles: list[ViewerProfile], crew: Crew) -> dict:
    state, event = _state_through(match, event_id)
    broadcasts = []
    for profile in profiles[:MAX_PROFILES]:
        job = Director(profile).plan(event, state)
        trace: list[dict] = []
        segments = []
        if job:
            segments = await crew.produce(
                job,
                profile,
                lambda agent, status, detail, ms, log=trace: log.append(
                    {"agent": agent, "status": status, "detail": detail, "ms": ms}
                ),
            )
        broadcasts.append(
            {
                "profile": profile.to_dict(),
                "kinds": list(job.kinds) if job else [],
                "segments": [s.to_dict() for s in segments],
                "trace": trace,
            }
        )
    return {"event": event.to_dict(), "state": state.snapshot(), "broadcasts": broadcasts}
