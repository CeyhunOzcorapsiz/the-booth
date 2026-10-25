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
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from booth import __version__, moment, qa, telemetry
from booth.agents import templates
from booth.crew import Crew
from booth.limits import LimitConfig, RateLimiter, StreamSlots, client_id
from booth.llm import LLMRuntime
from booth.orchestrator import Broadcast
from booth.profile import LANGUAGES, STYLES, ViewerProfile
from booth.sim.match import Match, generate_match
from booth.speech import Speech, SpeechUnavailable

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
speech = Speech()
limits = LimitConfig.from_env()
limiter = RateLimiter(limits.requests_per_minute)
slots = StreamSlots(limits.max_streams, limits.max_streams_per_client, limits.stream_lease_s)


def throttle(request: Request, cost: float = 1.0) -> None:
    """Per-client token bucket shared by every endpoint that costs CPU, model calls or speech."""
    if not limiter.allow(client_id(request, limits.trust_proxy), cost):
        raise HTTPException(429, "Too many requests. Please slow down.", headers={"Retry-After": "10"})


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
        "font-src https://fonts.gstatic.com; connect-src 'self'; img-src 'self' data:; media-src 'self' blob:; "
        "frame-ancestors 'none'"
    )
    return response


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "version": __version__,
        "synthetic": True,
        "llm": runtime.status(),
        "speech": speech.status(),
        "broadcasts": {"active": slots.active, "max": limits.max_streams},
    }


@app.get("/api/options")
def options() -> dict:
    return {"languages": LANGUAGES, "styles": list(STYLES), "offline_languages": list(templates.SUPPORTED)}


@app.get("/api/match")
def match_meta(request: Request, seed: Seed = 42) -> dict:
    throttle(request, 0.25)
    return match_for(seed).meta()


@app.get("/api/match/events")
def match_events(request: Request, seed: Seed = 42) -> dict:
    """Full synthetic event log, for analysis or download."""
    throttle(request, 0.25)
    match = match_for(seed)
    return {**match.meta(), "events": [e.to_dict() for e in match.events]}


@app.get("/api/broadcast")
async def broadcast(
    request: Request,
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
    throttle(request)
    lease = slots.acquire(client_id(request, limits.trust_proxy))
    if lease is None:
        raise HTTPException(429, "Too many live broadcasts right now. Close one or try again shortly.")
    show = Broadcast(match_for(seed), profile, crew, speed=speed, start_minute=start)

    async def sse():
        try:
            async for message in show.stream():
                yield f"event: {message['type']}\ndata: {json.dumps(message, ensure_ascii=False, default=str)}\n\n"
        finally:
            slots.release(lease)

    return StreamingResponse(
        sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class Question(BaseModel):
    seed: int = Field(42, ge=0, le=2**32 - 1)
    minute: float = Field(..., ge=0, le=100)
    period: int | None = Field(None, ge=1, le=2)
    question: str = Field(..., min_length=1, max_length=400)
    lang: str = "en"


@app.post("/api/ask")
async def ask(body: Question, request: Request) -> dict:
    throttle(request)
    if body.lang not in LANGUAGES:
        raise HTTPException(400, "Unsupported language.")
    return await qa.answer(match_for(body.seed), body.minute, body.question, body.lang, runtime, body.period)


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
def moments(request: Request, seed: Seed = 42) -> list[dict]:
    """Highlights worth comparing across viewer profiles."""
    throttle(request, 0.25)
    return moment.highlights(match_for(seed))


@app.post("/api/compare")
async def compare(body: CompareRequest, request: Request) -> dict:
    """Run several viewer profiles over the same moment and return each broadcast with its trace."""
    throttle(request, len(body.profiles or moment.PRESETS))
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


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=400)
    lang: str = "en"


@app.post("/api/tts", responses={200: {"content": {"audio/mpeg": {}}}})
async def tts(body: SpeakRequest, request: Request) -> Response:
    """Azure AI Speech neural voice for one line. 503 when not configured: the browser voice is used."""
    throttle(request)
    if body.lang not in LANGUAGES:
        raise HTTPException(400, "Unsupported language.")
    try:
        audio = await speech.synthesize(body.text, body.lang)
    except SpeechUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    return Response(audio, media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=3600"})


if FRONTEND.is_dir():
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(FRONTEND / "index.html")
