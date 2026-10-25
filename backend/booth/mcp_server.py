"""The Booth's stats desk and crew as a Model Context Protocol server.

Lets other agents (GitHub Copilot, Claude, a Foundry agent, ...) query synthetic matches and ask the crew to
broadcast a moment, with the same tools and fact-checking the booth uses internally.

    python -m booth.mcp_server                    # stdio, for local MCP clients
    python -m booth.mcp_server --http --port 8765 # streamable HTTP

Example client config (VS Code / GitHub Copilot ``.vscode/mcp.json``)::

    {"servers": {"the-booth": {"command": "backend/.venv/Scripts/python", "args": ["-m", "booth.mcp_server"]}}}
"""

from __future__ import annotations

import argparse
from functools import lru_cache

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from booth import moment, overlays, qa
from booth.crew import Crew
from booth.facts import StatsDesk
from booth.llm import LLMRuntime
from booth.profile import ViewerProfile
from booth.sim.match import Match, generate_match

MAX_EVENTS = 200
READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)

server = MCPServer(
    name="the-booth",
    title="The Booth: synthetic football stats desk",
    instructions=(
        "All matches are synthetic and generated from a seed (fictional clubs and players). "
        "Minutes above 45 refer to the second half. "
        "Use `highlights` to find moments, the stats tools for numbers at any minute, and `broadcast_moment` "
        "to have the fact-checked crew commentate a moment for a given language and style."
    ),
)
_crew: Crew | None = None


@lru_cache(maxsize=16)
def _match(seed: int) -> Match:
    return generate_match(seed)


def _desk(seed: int, minute: float) -> StatsDesk:
    # Minutes above 45 are read as second half; pass e.g. 45.9 for first-half stoppage time.
    return StatsDesk(qa.state_at(_match(seed), minute).freeze())


def _crew_instance() -> Crew:
    global _crew
    if _crew is None:
        _crew = Crew(LLMRuntime())
    return _crew


@server.tool(annotations=READ_ONLY)
def squads(seed: int = 119) -> dict:
    """Clubs and squads (player ids, numbers, names, positions) for the match generated from ``seed``."""
    return _match(seed).meta()


@server.tool(annotations=READ_ONLY)
def highlights(seed: int = 119) -> list[dict]:
    """Goals, penalties, red cards and big saves in the match, with their event ids."""
    return moment.highlights(_match(seed))


@server.tool(annotations=READ_ONLY)
def score(seed: int = 119, minute: float = 90) -> dict:
    """Score at a given match minute."""
    return _desk(seed, minute).score()


@server.tool(annotations=READ_ONLY)
def team_stats(team: str, seed: int = 119, minute: float = 90) -> dict:
    """A team's statistics at a given minute. ``team`` is 'home', 'away' or the club name."""
    return _desk(seed, minute).team_stats(team)


@server.tool(annotations=READ_ONLY)
def player_stats(player: str, seed: int = 119, minute: float = 90) -> dict:
    """A player's statistics at a given minute. ``player`` is an id like 'H9' or a name."""
    return _desk(seed, minute).player_stats(player)


@server.tool(annotations=READ_ONLY)
def storylines(seed: int = 119, minute: float = 90) -> dict:
    """Narratives the storyline agent has found so far: comebacks, late winners, braces, quick-fire goals."""
    return _desk(seed, minute).storylines()


@server.tool(annotations=READ_ONLY)
def events(seed: int = 119, from_minute: float = 0, to_minute: float = 95, types: str = "") -> dict:
    """Raw synthetic events between two minutes, optionally filtered by comma-separated ``types``
    (e.g. 'shot,goal'). At most 200 events are returned."""
    wanted = {t.strip() for t in types.split(",") if t.strip()}
    rows = [
        e.to_dict()
        for e in _match(seed).events
        if from_minute * 60 <= e.clock <= to_minute * 60 and (not wanted or e.type in wanted)
    ]
    return {"count": len(rows), "truncated": len(rows) > MAX_EVENTS, "events": rows[:MAX_EVENTS]}


@server.tool(annotations=READ_ONLY)
def overlay_cues(seed: int = 119, lang: str = "en", from_minute: float = 0, to_minute: float = 130) -> dict:
    """Timed, machine-readable overlay cues for broadcast graphics (lower thirds, stat cards, player tags)."""
    cues = overlays.build_cues(_match(seed), lang, from_minute, to_minute)
    return {"schema_version": overlays.SCHEMA_VERSION, "count": len(cues), "cues": cues[:MAX_EVENTS]}


@server.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
async def broadcast_moment(
    event_id: str,
    seed: int = 119,
    lang: str = "en",
    style: str = "hype",
    accessible: bool = False,
    club: str | None = None,
) -> dict:
    """Have the booth's crew broadcast one moment (event id from ``highlights``) for a viewer profile.
    Returns the fact-checked segments and every agent hand-off. Uses a model if one is configured."""
    profile = ViewerProfile(lang=lang, style=style, accessible=accessible, club=club)
    result = await moment.compare(_match(seed), event_id, [profile], _crew_instance())
    return result["broadcasts"][0] | {"event": result["event"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run The Booth as an MCP server.")
    parser.add_argument("--http", action="store_true", help="serve streamable HTTP instead of stdio")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.http:
        server.run("streamable-http", port=args.port)
    else:
        server.run("stdio")


if __name__ == "__main__":
    main()
