import httpx
import pytest
from fastapi.testclient import TestClient

from booth import api
from booth.limits import DailyBudget, RateLimiter, StreamSlots, client_id
from booth.llm import LLMConfig, LLMRuntime, LLMUnavailable
from booth.speech import Speech, SpeechUnavailable


class FakeRequest:
    def __init__(self, host="10.0.0.1", forwarded=None):
        self.client = type("C", (), {"host": host})()
        self.headers = {"x-forwarded-for": forwarded} if forwarded else {}


def test_client_id_only_trusts_the_proxy_appended_address():
    request = FakeRequest(forwarded="1.2.3.4, 203.0.113.9")
    assert client_id(request, trust_proxy=True) == "203.0.113.9"
    assert client_id(request, trust_proxy=False) == "10.0.0.1"


def test_rate_limiter_blocks_bursts_per_client():
    limiter = RateLimiter(per_minute=3)
    assert all(limiter.allow("a") for _ in range(3))
    assert not limiter.allow("a")
    assert limiter.allow("b")
    assert not limiter.allow("c", cost=4)


def test_stream_slots_cap_total_and_per_client_and_release():
    slots = StreamSlots(max_total=3, max_per_client=2, lease_s=60)
    a1, a2 = slots.acquire("a"), slots.acquire("a")
    assert a1 and a2 and slots.acquire("a") is None
    assert slots.acquire("b")
    assert slots.acquire("c") is None  # total cap
    slots.release(a1)
    assert slots.acquire("c")


def test_stream_leases_expire():
    slots = StreamSlots(max_total=1, max_per_client=1, lease_s=-1)
    assert slots.acquire("a")
    assert slots.acquire("a")  # previous lease already expired


async def test_daily_budget_stops_model_calls():
    budget = DailyBudget(2)
    assert budget.take() and budget.take() and not budget.take()
    runtime = LLMRuntime(LLMConfig(provider="t", model="m", api_key="k", daily_budget=1), client=object())
    runtime.budget.take()
    assert not runtime.available()
    with pytest.raises(LLMUnavailable):
        await runtime.run("x", "y", "z")
    assert runtime.status()["budget"] == {"daily_limit": 1, "used_today": 1}


def test_broadcast_returns_429_when_slots_are_full(monkeypatch):
    monkeypatch.setattr(api, "slots", StreamSlots(max_total=0, max_per_client=1, lease_s=60))
    assert TestClient(api.app).get("/api/broadcast?seed=1").status_code == 429


def test_endpoints_are_rate_limited(monkeypatch):
    monkeypatch.setattr(api, "limiter", RateLimiter(per_minute=2))
    client = TestClient(api.app)
    body = {"seed": 1, "minute": 10, "question": "score?"}
    codes = [client.post("/api/ask", json=body).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


async def test_speech_sends_ssml_with_key_and_caches():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=b"mp3-bytes")

    speech = Speech(key="k", region="westeurope", daily_chars=1000, transport=httpx.MockTransport(handler))
    assert await speech.synthesize("Gol! <Vale>", "tr") == b"mp3-bytes"
    assert await speech.synthesize("Gol! <Vale>", "tr") == b"mp3-bytes"
    assert len(seen) == 1
    request = seen[0]
    assert request.url.host == "westeurope.tts.speech.microsoft.com"
    assert request.headers["Ocp-Apim-Subscription-Key"] == "k"
    body = request.content.decode()
    assert "tr-TR-AhmetNeural" in body and "&lt;Vale&gt;" in body


async def test_speech_budget_and_unconfigured():
    with pytest.raises(SpeechUnavailable):
        await Speech(key="", region="").synthesize("hi", "en")
    speech = Speech(
        key="k",
        region="r",
        daily_chars=5,
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"x")),
    )
    with pytest.raises(SpeechUnavailable):
        await speech.synthesize("too long for the budget", "en")


def test_tts_endpoint_is_503_without_speech_config(monkeypatch):
    monkeypatch.setattr(api, "speech", Speech(key="", region=""))
    response = TestClient(api.app).post("/api/tts", json={"text": "Hello", "lang": "en"})
    assert response.status_code == 503
