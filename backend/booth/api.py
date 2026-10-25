"""HTTP API and static frontend for The Booth."""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from booth import __version__, moment, qa, telemetry
from booth.agents import templates
from booth.crew import Crew
from booth.llm import LLMRuntime
from booth.orchestrator import Broadcast
from booth.profile import LANGUAGES, STYLES, ViewerProfile
from booth.sim.match import Match, generate_match

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
telemetry.configure()

FRONTEND = Path(os.getenv("BOOTH_FRONTEND_DIR", Path(__file__).resolve().parents[2] / "frontend"))
Seed = Annotated[int, Query(ge=0, le=2**32 - 1)]

app = FastAPI(
    title="The Booth", version=__version__, description="An AI broadcast crew for synthetic football matches."
)
runtime = LLMRuntime()
crew = Crew(runtime)


@lru_cache(maxsize=32)
def match_for(seed: int) -> Match:
    return generate_match(seed)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
    )
    return response


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "version": __version__, "synthetic": True, "llm": runtime.status()}


@app.get("/api/options")
def options() -> dict:
    return {"languages": LANGUAGES, "styles": list(STYLES), "offline_languages": list(templates.SUPPORTED)}


@app.get("/api/match")
def match_meta(seed: Seed = 42) -> dict:
    return match_for(seed).meta()


@app.get("/api/match/events")
def match_events(seed: Seed = 42) -> dict:
    """Full synthetic event log, for analysis or download."""
    match = match_for(seed)
    return {**match.meta(), "events": [e.to_dict() for e in match.events]}


@app.get("/api/broadcast")
async def broadcast(
    seed: Seed = 42,
    lang: str = "en",
    style: str = "hype",
    accessible: bool = False,
    follow: str | None = None,
    speed: Annotated[float, Query(gt=0, le=600)] = 20.0,
    start: Annotated[float, Query(ge=0, le=95)] = 0.0,
) -> StreamingResponse:
    try:
        profile = ViewerProfile(lang=lang, style=style, accessible=accessible, follow=follow or None)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    show = Broadcast(match_for(seed), profile, crew, speed=speed, start_minute=start)

    async def sse():
        async for message in show.stream():
            yield f"event: {message['type']}\ndata: {json.dumps(message, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(
        sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class Question(BaseModel):
    seed: int = Field(42, ge=0, le=2**32 - 1)
    minute: float = Field(..., ge=0, le=100)
    question: str = Field(..., min_length=1, max_length=400)
    lang: str = "en"


@app.post("/api/ask")
async def ask(body: Question) -> dict:
    if body.lang not in LANGUAGES:
        raise HTTPException(400, "Unsupported language.")
    return await qa.answer(match_for(body.seed), body.minute, body.question, body.lang, runtime)


class ProfileIn(BaseModel):
    lang: str = "en"
    style: str = "hype"
    accessible: bool = False
    follow: str | None = None


class CompareRequest(BaseModel):
    seed: int = Field(42, ge=0, le=2**32 - 1)
    event_id: str = Field(..., pattern=r"^E\d{4}$")
    profiles: list[ProfileIn] | None = Field(None, max_length=moment.MAX_PROFILES)


@app.get("/api/moments")
def moments(seed: Seed = 42) -> list[dict]:
    """Highlights worth comparing across viewer profiles."""
    return moment.highlights(match_for(seed))


@app.post("/api/compare")
async def compare(body: CompareRequest) -> dict:
    """Run several viewer profiles over the same moment and return each broadcast with its trace."""
    try:
        profiles = (
            [ViewerProfile(**p.model_dump()) for p in body.profiles]
            if body.profiles
            else list(moment.PRESETS)
        )
        return await moment.compare(match_for(body.seed), body.event_id, profiles, crew)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(404, "Unknown event.") from exc


if FRONTEND.is_dir():
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(FRONTEND / "index.html")
