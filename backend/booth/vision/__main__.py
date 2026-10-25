"""Render a clip, run auto-eventing on the video file, and score it.

    python -m booth.vision --seed 119 --start 76 --minutes 3 --out ../vision-out
    python -m booth.vision --benchmark --out ../vision-bench     # several clips, aggregated

The detector reads the encoded MP4 back from disk, so it only ever sees pixels.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from booth.sim import generate_match
from booth.sim.tracking import absolute, tracking_for
from booth.vision.autoevent import analyse
from booth.vision.evaluate import KINDS, report
from booth.vision.groundtruth import FPS, build
from booth.vision.render import read_video, render_frames, write_video

BENCHMARK = [(119, 2, 76), (119, 1, 18), (3, 1, 30), (3, 2, 60), (42, 1, 10), (42, 2, 70)]


def _score_at(match):
    """Scoreboard text for a frame: (minute, home goals, away goals)."""
    goals = [(absolute(e.period, e.clock), e.team) for e in match.events if e.type == "goal"]

    def score(frame):
        home = sum(1 for t, team in goals if t <= frame.t and team == "home")
        away = sum(1 for t, team in goals if t <= frame.t and team == "away")
        return f"{int(frame.clock // 60) + 1}'", home, away

    return score


def run_clip(seed: int, period: int, start_minute: float, minutes: float, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    match = generate_match(seed)
    start, end = start_minute * 60, (start_minute + minutes) * 60
    frames, truth = build(match, tracking_for(match), period, start, end)
    video = out / f"clip-{seed}-{period}-{int(start_minute)}.mp4"
    t0 = time.perf_counter()
    write_video(render_frames(match, frames, _score_at(match), seed=seed), str(video))
    rendered = time.perf_counter() - t0
    t0 = time.perf_counter()
    result = analyse(list(read_video(str(video))), FPS)
    analysed = time.perf_counter() - t0
    scores = report(result.detections, truth, absolute(period, start), result.homography)
    clip0 = absolute(period, start)
    payload = {
        "clip": {
            "seed": seed,
            "period": period,
            "start_minute": start_minute,
            "minutes": minutes,
            "video": video.name,
            "fps": FPS,
            "render_s": round(rendered, 1),
            "analyse_s": round(analysed, 1),
        },
        "report": scores,
        "pipeline": result.stats,
        "detections": [d.to_dict() for d in result.detections],
        "truth": [
            {
                "kind": e.kind,
                "t": round(e.t - clip0, 2),
                "team": e.team,
                "distance_m": e.distance_m,
                "speed_kmh": e.speed_kmh,
            }
            for e in truth
        ],
    }
    (out / video.with_suffix(".json").name).write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return payload


def aggregate(runs: list[dict]) -> dict:
    totals = {k: {"truth": 0, "detected": 0, "matched": 0} for k in KINDS}
    speed, distance, speed_med, distance_med = [], [], [], []
    for run in runs:
        for kind in KINDS:
            for key in ("truth", "detected", "matched"):
                totals[kind][key] += run["report"]["events"][kind][key]
        if run["report"]["pass_speed_mae_kmh"] is not None:
            speed.append(run["report"]["pass_speed_mae_kmh"])
            distance.append(run["report"]["pass_distance_mae_m"])
            speed_med.append(run["report"]["pass_speed_median_error_kmh"])
            distance_med.append(run["report"]["pass_distance_median_error_m"])
    for t in totals.values():
        p = t["matched"] / t["detected"] if t["detected"] else None
        r = t["matched"] / t["truth"] if t["truth"] else None
        t["precision"] = None if p is None else round(p, 3)
        t["recall"] = None if r is None else round(r, 3)
        t["f1"] = round(2 * p * r / (p + r), 3) if p and r else None
    return {
        "clips": len(runs),
        "events": totals,
        "pass_speed_mae_kmh": round(sum(speed) / len(speed), 1) if speed else None,
        "pass_distance_mae_m": round(sum(distance) / len(distance), 2) if distance else None,
        "pass_speed_median_error_kmh": round(sorted(speed_med)[len(speed_med) // 2], 1)
        if speed_med
        else None,
        "pass_distance_median_error_m": round(sorted(distance_med)[len(distance_med) // 2], 2)
        if distance_med
        else None,
        "calibration_error_m": max(r["report"]["calibration_error_m"] for r in runs),
    }


def markdown(summary: dict, runs: list[dict]) -> str:
    lines = [
        "# Auto-eventing benchmark",
        "",
        f"{summary['clips']} clips of synthetic video, scored against the events they were rendered from "
        f"(±{runs[0]['report']['tolerance_s']} s, same team).",
        "",
        "| Event | Truth | Detected | Matched | Precision | Recall | F1 |",
        "|---|---|---|---|---|---|---|",
    ]
    for kind, t in summary["events"].items():
        lines.append(
            f"| {kind} | {t['truth']} | {t['detected']} | {t['matched']} | {t['precision']} | "
            f"{t['recall']} | {t['f1']} |"
        )
    lines += [
        "",
        f"- Pass ball speed error: median {summary['pass_speed_median_error_kmh']} km/h, "
        f"mean {summary['pass_speed_mae_kmh']} km/h",
        f"- Pass distance error: median {summary['pass_distance_median_error_m']} m, "
        f"mean {summary['pass_distance_mae_m']} m",
        f"- Camera calibration error (worst clip): {summary['calibration_error_m']} m",
        "",
        "## Clips",
        "",
    ]
    for run in runs:
        c, ev = run["clip"], run["report"]["events"]
        lines.append(
            f"- seed {c['seed']}, half {c['period']}, from {c['start_minute']}' for {c['minutes']} min: "
            f"pass F1 {ev['pass']['f1']}, turnover F1 {ev['turnover']['f1']}, shot F1 {ev['shot']['f1']}"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic video -> auto-eventing -> score.")
    parser.add_argument("--seed", type=int, default=119)
    parser.add_argument("--period", type=int, default=2)
    parser.add_argument("--start", type=float, default=76)
    parser.add_argument("--minutes", type=float, default=3)
    parser.add_argument("--out", default="vision-out")
    parser.add_argument("--benchmark", action="store_true")
    args = parser.parse_args()
    out = Path(args.out)
    if args.benchmark:
        runs = [run_clip(seed, period, start, args.minutes, out) for seed, period, start in BENCHMARK]
        summary = aggregate(runs)
        (out / "benchmark.json").write_text(
            json.dumps({"summary": summary, "runs": [r["report"] for r in runs]}, indent=1), encoding="utf-8"
        )
        text = markdown(summary, runs)
        (out / "BENCHMARK.md").write_text(text, encoding="utf-8")
        print(text)
    else:
        print(json.dumps(run_clip(args.seed, args.period, args.start, args.minutes, out)["report"], indent=1))


if __name__ == "__main__":
    main()
