"""Shared types for the crew."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field

from booth.sim.match import MatchEvent
from booth.state import FrozenState

TraceFn = Callable[[str, str, str, int], None]


@dataclass(frozen=True)
class Job:
    """A unit of broadcast work planned by the director for one event."""

    id: str
    event: MatchEvent
    kinds: tuple[str, ...]
    importance: float
    state: FrozenState


@dataclass
class Segment:
    """Something that goes on air for a viewer."""

    job: str
    kind: str
    speaker: str
    text: str
    lang: str
    source: str
    verified: bool
    event_id: str
    minute: str
    importance: float
    evidence: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


SPEAKERS = {
    "pbp": "Play-by-play",
    "color": "Analyst",
    "stats": "Stats desk",
    "explain": "Guide",
    "spatial": "Guide",
    "recap": "Recap editor",
}


class Timer:
    def __init__(self):
        self.start = time.perf_counter()

    @property
    def ms(self) -> int:
        return int((time.perf_counter() - self.start) * 1000)
