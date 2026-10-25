"""Build a static demo of The Booth (no server, no model) for GitHub Pages.

    python -m booth.static_site --out ../_site

Records the demo match for a set of viewer profiles with the offline crew, so judges can open a link and
watch it. The match timeline (events + shared state) is written once; each profile only stores its own
segments, traces and overlay cues. Comparisons are recorded for every highlight and profile.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
from pathlib import Path

from booth import __version__, moment
from booth.agents import templates
from booth.crew import Crew
from booth.orchestrator import Broadcast
from booth.profile import LANGUAGES, STYLES, ViewerProfile
from booth.sim.match import generate_match

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
DEMO_SEED = 119
PROFILES = [
    ViewerProfile("en", "hype"),
    ViewerProfile("en", "calm"),
    ViewerProfile("en", "tactical"),
    ViewerProfile("en", "beginner"),
    ViewerProfile("en", "beginner", accessible=True),
    ViewerProfile("en", "hype", club="home"),
    ViewerProfile("en", "hype", club="away"),
    ViewerProfile("tr", "hype"),
    ViewerProfile("tr", "calm"),
    ViewerProfile("tr", "tactical"),
    ViewerProfile("tr", "beginner", accessible=True),
    ViewerProfile("tr", "hype", club="home"),
]


def key(profile: ViewerProfile) -> str:
    return f"{profile.lang}-{profile.style}-{int(profile.accessible)}-{profile.club or 'none'}"


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


async def _record(match, profile: ViewerProfile, crew: Crew) -> tuple[list, dict]:
    timeline, messages, hello = [], [], None
    index = -1
    show = Broadcast(match, profile, crew, speed=1e9, max_gap_s=0, drop_stale=False)
    async for message in show.stream():
        if message["type"] == "hello":
            hello = message
        elif message["type"] == "event":
            index += 1
            timeline.append({"event": message["event"], "state": message["state"]})
        elif message["type"] != "end":
            messages.append({"i": max(index, 0), **message})
    return timeline, {"hello": hello, "messages": messages}


async def build(out: Path) -> dict:
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(FRONTEND, out)
    index = (out / "index.html").read_text(encoding="utf-8")
    index = index.replace('<html lang="en">', '<html lang="en" data-static="1">').replace("/static/", "./")
    (out / "index.html").write_text(index, encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")

    data = out / "data"
    match = generate_match(DEMO_SEED)
    crew = Crew(None)
    _write(
        data / "options.json",
        {"languages": LANGUAGES, "styles": list(STYLES), "offline_languages": list(templates.SUPPORTED)},
    )
    _write(
        data / "health.json",
        {
            "ok": True,
            "version": __version__,
            "synthetic": True,
            "static": True,
            "llm": {"provider": "offline", "model": None, "configured": False},
            "speech": {"enabled": False, "provider": "browser"},
        },
    )
    _write(data / "match.json", match.meta())
    highlights = moment.highlights(match)
    _write(data / "moments.json", highlights)

    timeline = None
    for profile in PROFILES:
        recorded_timeline, recording = await _record(match, profile, crew)
        timeline = timeline or recorded_timeline
        _write(data / "broadcast" / f"{key(profile)}.json", recording)

    _write(data / "timeline.json", timeline)
    for highlight in highlights:
        for profile in PROFILES:
            result = await moment.compare(match, highlight["event_id"], [profile], crew)
            _write(
                data / "compare" / f"{highlight['event_id']}__{key(profile)}.json",
                {"event": result["event"], "state": result["state"], "broadcast": result["broadcasts"][0]},
            )

    manifest = {
        "seed": DEMO_SEED,
        "version": __version__,
        "profiles": [p.to_dict() for p in PROFILES],
        "highlights": [h["event_id"] for h in highlights],
    }
    _write(data / "manifest.json", manifest)
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    return {
        "out": str(out.resolve()),
        "profiles": len(PROFILES),
        "highlights": len(highlights),
        "events": len(timeline),
        "size_mb": round(size / 1e6, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the static GitHub Pages demo.")
    parser.add_argument("--out", default="_site")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(build(Path(args.out))), indent=2))


if __name__ == "__main__":
    main()
