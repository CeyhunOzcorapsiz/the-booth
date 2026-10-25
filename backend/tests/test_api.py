import json

from fastapi.testclient import TestClient

from booth.api import app

client = TestClient(app)


def test_health_and_options():
    body = client.get("/api/health").json()
    assert body["ok"] and body["synthetic"]
    assert "tr" in client.get("/api/options").json()["languages"]


def test_match_meta_and_events():
    meta = client.get("/api/match?seed=9").json()
    assert meta["teams"]["home"]["name"] == "Northstar FC"
    assert len(meta["teams"]["away"]["players"]) == 16
    events = client.get("/api/match/events?seed=9").json()["events"]
    assert events[-1]["type"] == "full_time"
    assert client.get("/api/match?seed=-1").status_code == 422


def test_broadcast_streams_server_sent_events():
    types = []
    with client.stream("GET", "/api/broadcast?seed=9&speed=600&start=88&lang=tr&style=calm") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        for line in response.iter_lines():
            if line.startswith("data: "):
                message = json.loads(line[6:])
                types.append(message["type"])
                if message["type"] == "end":
                    break
    assert types[0] == "hello" and types[-1] == "end"
    assert "segment" in types and "trace" in types


def test_broadcast_rejects_bad_profiles():
    assert client.get("/api/broadcast?lang=xx").status_code == 400
    assert client.get("/api/broadcast?style=loud").status_code == 400
    assert client.get("/api/broadcast?follow=Z99").status_code == 400


def test_ask_answers_from_the_stats_desk():
    body = client.post(
        "/api/ask", json={"seed": 9, "minute": 60, "question": "Who has more possession?"}
    ).json()
    assert body["source"] == "template" and body["evidence"]
    assert client.post("/api/ask", json={"minute": 60, "question": ""}).status_code == 422


def test_moments_and_side_by_side_compare():
    highlights = client.get("/api/moments?seed=9").json()
    goal = next(h for h in highlights if h["type"] == "goal")
    body = client.post("/api/compare", json={"seed": 9, "event_id": goal["event_id"]}).json()
    assert body["event"]["id"] == goal["event_id"]
    assert len(body["broadcasts"]) == 3
    texts = [b["segments"][0]["text"] for b in body["broadcasts"]]
    assert len(set(texts)) == 3  # same goal, three different shows
    assert all(b["trace"] for b in body["broadcasts"])
    custom = client.post(
        "/api/compare",
        json={"seed": 9, "event_id": goal["event_id"], "profiles": [{"lang": "tr", "style": "calm"}]},
    ).json()
    assert custom["broadcasts"][0]["segments"][0]["lang"] == "tr"
    assert client.post("/api/compare", json={"seed": 9, "event_id": "E9999"}).status_code == 404
    assert client.post("/api/compare", json={"seed": 9, "event_id": "x"}).status_code == 422


async def test_mcp_server_exposes_the_stats_desk_and_crew():
    import json as _json

    from booth.mcp_server import server

    names = {t.name for t in await server.list_tools()}
    assert {"highlights", "score", "storylines", "broadcast_moment"} <= names
    result = await server.call_tool("score", {"seed": 119, "minute": 95})
    assert _json.loads(result.content[0].text)["home_goals"] == 3
    winner = _json.loads((await server.call_tool("highlights", {"seed": 119})).content[-1].text)
    show = await server.call_tool("broadcast_moment", {"seed": 119, "event_id": winner["event_id"]})
    body = _json.loads(show.content[0].text)
    assert body["segments"] and body["trace"]
