"""Export synthetic matches as an analytics-ready dataset (CSV + JSONL), e.g. for Microsoft Fabric or pandas.

    python -m booth.dataset --matches 200 --first-seed 1 --out ../data/synthetic

Writes four tables that join on ``match_id`` / ``player_id``:

* ``matches.csv``  – one row per match: score, shots, possession, storylines
* ``events.csv``   – one row per event (also ``events.jsonl`` with the nested ``detail``)
* ``players.csv``  – squads: one row per player per match, with per-match counters
* ``storylines.csv`` – narratives the storyline agent found

Everything is fictional and generated from seeds, so the dataset can be shared freely.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from booth.sim.match import generate_match
from booth.sim.tracking import tracking_for_seed
from booth.state import MatchState

EVENT_FIELDS = [
    "match_id",
    "event_id",
    "period",
    "clock_s",
    "minute",
    "display_minute",
    "type",
    "team",
    "player_id",
    "target_id",
    "x",
    "y",
    "end_x",
    "end_y",
    "outcome",
    "possession",
    "phase",
    "distance_m",
    "chance_quality",
    "body_part",
    "situation",
    "pass_distance_m",
    "progressive_m",
    "difficulty",
    "ball_speed_kmh",
]
MATCH_FIELDS = [
    "match_id",
    "seed",
    "home",
    "away",
    "home_goals",
    "away_goals",
    "home_shots",
    "away_shots",
    "home_on_target",
    "away_on_target",
    "home_possession_pct",
    "away_possession_pct",
    "home_corners",
    "away_corners",
    "home_fouls",
    "away_fouls",
    "home_cards",
    "away_cards",
    "events",
    "storylines",
]
PLAYER_FIELDS = [
    "match_id",
    "player_id",
    "team",
    "club",
    "number",
    "name",
    "position",
    "starter",
    "passes",
    "shots",
    "shots_on_target",
    "goals",
    "assists",
    "tackles",
    "interceptions",
    "fouls",
    "saves",
    "yellow_cards",
    "red_cards",
    "distance_km",
    "top_speed_kmh",
    "sprints",
    "high_intensity_m",
]
TRACKING_FIELDS = ["match_id", "period", "clock_s", "player_id", "x", "y", "speed_kmh"]
STORY_FIELDS = [
    "match_id",
    "storyline_id",
    "event_id",
    "minute",
    "kind",
    "team",
    "player_id",
    "text_en",
    "text_tr",
]


def match_rows(seed: int) -> dict[str, list[dict]]:
    match = generate_match(seed)
    match_id = f"M{seed:06d}"
    state = MatchState(match)
    events = []
    for e in match.events:
        state.apply(e)
        events.append(
            {
                "match_id": match_id,
                "event_id": e.id,
                "period": e.period,
                "clock_s": e.clock,
                "minute": e.minute,
                "display_minute": e.display_minute,
                "type": e.type,
                "team": e.team,
                "player_id": e.player,
                "target_id": e.target,
                "x": e.x,
                "y": e.y,
                "end_x": e.end_x,
                "end_y": e.end_y,
                "outcome": e.outcome,
                "possession": e.possession,
                "phase": e.phase,
                "distance_m": e.detail.get("distance_m"),
                "chance_quality": e.detail.get("chance_quality"),
                "body_part": e.detail.get("body_part"),
                "situation": e.detail.get("situation"),
                "pass_distance_m": e.detail.get("pass_distance_m"),
                "progressive_m": e.detail.get("progressive_m"),
                "difficulty": e.detail.get("difficulty"),
                "ball_speed_kmh": e.detail.get("ball_speed_kmh"),
                "detail": e.detail,
            }
        )
    snap = state.snapshot()
    h, a = snap["teams"]["home"], snap["teams"]["away"]
    stories = state.story.storylines
    summary = {
        "match_id": match_id,
        "seed": seed,
        "home": match.teams["home"].name,
        "away": match.teams["away"].name,
        "home_goals": h["goals"],
        "away_goals": a["goals"],
        "home_shots": h["shots"],
        "away_shots": a["shots"],
        "home_on_target": h["shots_on_target"],
        "away_on_target": a["shots_on_target"],
        "home_possession_pct": h["possession_pct"],
        "away_possession_pct": a["possession_pct"],
        "home_corners": h["corners"],
        "away_corners": a["corners"],
        "home_fouls": h["fouls"],
        "away_fouls": a["fouls"],
        "home_cards": h["yellow_cards"] + h["red_cards"],
        "away_cards": a["yellow_cards"] + a["red_cards"],
        "events": len(match.events),
        "storylines": ";".join(s.kind for s in stories),
    }
    players = []
    for team in match.teams.values():
        for p in team.players:
            counters = state.players.get(p.id, {})
            players.append(
                {
                    "match_id": match_id,
                    "player_id": p.id,
                    "team": team.id,
                    "club": team.name,
                    "number": p.number,
                    "name": p.name,
                    "position": p.position,
                    "starter": p.starter,
                    **{k: int(counters.get(k, 0)) for k in PLAYER_FIELDS[8:-4]},
                    **state.tracking.stats_until(p.id, 2, 1e9),
                }
            )
    story_rows = [
        {
            "match_id": match_id,
            "storyline_id": s.id,
            "event_id": s.event_id,
            "minute": s.minute,
            "kind": s.kind,
            "team": s.team,
            "player_id": s.player,
            "text_en": s.en,
            "text_tr": s.tr,
        }
        for s in stories
    ]
    return {"matches": [summary], "events": events, "players": players, "storylines": story_rows}


def tracking_rows(seed: int) -> list[dict]:
    """1 Hz positions and speeds of every player (about 125,000 rows per match)."""
    tracking = tracking_for_seed(seed)
    rows = []
    for pid, track in tracking.players.items():
        for t, (x, y), speed in zip(track.times, track.xy, track.speed, strict=True):
            period = 2 if t >= 10_000 else 1
            rows.append(
                {
                    "match_id": f"M{seed:06d}",
                    "period": period,
                    "clock_s": round(t - (10_000 if period == 2 else 0), 1),
                    "player_id": pid,
                    "x": round(x, 2),
                    "y": round(y, 2),
                    "speed_kmh": round(speed, 1),
                }
            )
    return rows


def export(first_seed: int, matches: int, out: Path, with_tracking: bool = False) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    tables = {
        "matches": (MATCH_FIELDS, open(out / "matches.csv", "w", newline="", encoding="utf-8")),
        "events": (EVENT_FIELDS, open(out / "events.csv", "w", newline="", encoding="utf-8")),
        "players": (PLAYER_FIELDS, open(out / "players.csv", "w", newline="", encoding="utf-8")),
        "storylines": (STORY_FIELDS, open(out / "storylines.csv", "w", newline="", encoding="utf-8")),
    }
    writers = {}
    for name, (fields, fh) in tables.items():
        writers[name] = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writers[name].writeheader()
    counts = dict.fromkeys(tables, 0)
    tracking_file = open(out / "tracking.csv", "w", newline="", encoding="utf-8") if with_tracking else None
    if tracking_file:
        tracking_writer = csv.DictWriter(tracking_file, fieldnames=TRACKING_FIELDS)
        tracking_writer.writeheader()
        counts["tracking"] = 0
    with open(out / "events.jsonl", "w", encoding="utf-8") as jsonl:
        for seed in range(first_seed, first_seed + matches):
            rows = match_rows(seed)
            for name, items in rows.items():
                writers[name].writerows(items)
                counts[name] += len(items)
            for event in rows["events"]:
                jsonl.write(json.dumps(event, ensure_ascii=False) + "\n")
            if tracking_file:
                samples = tracking_rows(seed)
                tracking_writer.writerows(samples)
                counts["tracking"] += len(samples)
    for _, fh in tables.values():
        fh.close()
    if tracking_file:
        tracking_file.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Export synthetic matches as CSV and JSONL.")
    parser.add_argument("--matches", type=int, default=50)
    parser.add_argument("--first-seed", type=int, default=1)
    parser.add_argument("--out", default="synthetic-data")
    parser.add_argument("--tracking", action="store_true", help="also write 1 Hz player tracking (large)")
    args = parser.parse_args()
    counts = export(args.first_seed, args.matches, Path(args.out), with_tracking=args.tracking)
    print(json.dumps({"out": str(Path(args.out).resolve()), **counts}, indent=2))


if __name__ == "__main__":
    main()
