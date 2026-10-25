"""Measure the crew on a whole match: how often model drafts pass the fact-checker, why they fail, where
the crew falls back to templates, and how long each agent takes.

    python -m booth.evaluate --seed 119 --profiles en:hype,tr:beginner:accessible --out eval.md

Runs with whatever provider ``.env`` configures (offline gives a template-only baseline). Live play is
not simulated, so no job is dropped for being late.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from dotenv import load_dotenv

from booth.crew import Crew
from booth.llm import LLMRuntime
from booth.orchestrator import Broadcast
from booth.profile import ViewerProfile
from booth.sim.match import generate_match


@dataclass
class Report:
    profile: str
    segments: Counter = field(default_factory=Counter)
    sources: Counter = field(default_factory=Counter)
    statuses: Counter = field(default_factory=Counter)
    rejections: Counter = field(default_factory=Counter)
    fallbacks: Counter = field(default_factory=Counter)
    latency: dict = field(default_factory=lambda: defaultdict(list))
    examples: list = field(default_factory=list)
    seconds: float = 0.0

    def to_dict(self) -> dict:
        checks = self.statuses["fact-checker:approved"] + self.statuses["fact-checker:rejected"]
        return {
            "profile": self.profile,
            "segments": dict(self.segments),
            "sources": dict(self.sources),
            "fact_check_pass_rate": round(self.statuses["fact-checker:approved"] / checks, 3)
            if checks
            else None,
            "rejection_reasons": dict(self.rejections.most_common(10)),
            "fallbacks": dict(self.fallbacks.most_common(10)),
            "latency_ms_median": {a: int(statistics.median(v)) for a, v in self.latency.items() if v},
            "examples": self.examples[:8],
            "seconds": round(self.seconds, 1),
        }


def parse_profile(spec: str) -> ViewerProfile:
    parts = spec.split(":")
    return ViewerProfile(
        lang=parts[0], style=parts[1] if len(parts) > 1 else "hype", accessible="accessible" in parts
    )


async def evaluate(seed: int, profiles: list[ViewerProfile], runtime: LLMRuntime) -> list[Report]:
    match = generate_match(seed)
    crew = Crew(runtime)
    reports = []
    for profile in profiles:
        report = Report(profile.key())
        started = time.perf_counter()
        show = Broadcast(match, profile, crew, speed=1e9, max_gap_s=0, drop_stale=False)
        async for message in show.stream():
            if message["type"] == "trace":
                agent, status = message["agent"], message["status"]
                report.statuses[f"{agent}:{status}"] += 1
                if status == "rejected":
                    for reason in message["detail"].split("; "):
                        report.rejections[reason.split(" is not")[0][:60]] += 1
                if status == "fallback":
                    report.fallbacks[f"{agent}: {message['detail'][:60]}"] += 1
                if message["ms"]:
                    report.latency[agent].append(message["ms"])
            elif message["type"] == "segment":
                report.segments[message["kind"]] += 1
                report.sources[message["source"]] += 1
                if message["source"] == "ai" and message["importance"] >= 0.9:
                    report.examples.append(f"[{message['kind']}] {message['text']}")
        report.seconds = time.perf_counter() - started
        reports.append(report)
    return reports


def to_markdown(seed: int, runtime: LLMRuntime, reports: list[Report]) -> str:
    status = runtime.status()
    lines = [
        f"# Crew evaluation · seed {seed}",
        "",
        f"Provider: `{status['provider']}` · model: `{status['model']}` · agent runs: {status['calls']} · "
        f"errors: {status['errors']}",
        "",
    ]
    for report in reports:
        data = report.to_dict()
        lines += [
            f"## {data['profile']}",
            "",
            f"- Segments: {data['segments']}",
            f"- Sources: {data['sources']}",
            f"- Fact-check pass rate: {data['fact_check_pass_rate']}",
            f"- Rejection reasons: {data['rejection_reasons'] or 'none'}",
            f"- Fallbacks: {data['fallbacks'] or 'none'}",
            f"- Median latency (ms): {data['latency_ms_median'] or 'n/a'}",
            f"- Wall time: {data['seconds']} s",
            "",
        ]
        if data["examples"]:
            lines += ["Examples:", ""] + [f"> {e}" for e in data["examples"]] + [""]
    return "\n".join(lines)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--seed", type=int, default=119)
    parser.add_argument("--profiles", default="en:hype,tr:beginner:accessible,en:tactical")
    parser.add_argument("--out", help="write the markdown report here")
    parser.add_argument("--json", action="store_true", help="print JSON instead of markdown")
    args = parser.parse_args()
    runtime = LLMRuntime()
    profiles = [parse_profile(p) for p in args.profiles.split(",")]
    reports = asyncio.run(evaluate(args.seed, profiles, runtime))
    if args.json:
        print(json.dumps([r.to_dict() for r in reports], indent=2, ensure_ascii=False))
        return
    text = to_markdown(args.seed, runtime, reports)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(text)


if __name__ == "__main__":
    main()
