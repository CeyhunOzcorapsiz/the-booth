"""The demo clip for the web app: built once in the background, then served from a cache directory."""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path

log = logging.getLogger("booth.vision")

DEMO = {"seed": 119, "period": 2, "start": 76, "minutes": 3}
CACHE = Path(os.getenv("BOOTH_VISION_DIR", Path(__file__).resolve().parents[2] / ".vision-cache"))
_lock = threading.Lock()
_state = {"building": False, "error": None}


def available() -> str | None:
    """None if the vision extras are installed, otherwise the reason."""
    try:
        import cv2  # noqa: F401
        import imageio_ffmpeg  # noqa: F401
    except ImportError:
        return 'Install the vision extra: pip install -e ".[vision]"'
    return None


def paths(cache: Path = CACHE) -> tuple[Path, Path]:
    name = f"clip-{DEMO['seed']}-{DEMO['period']}-{DEMO['start']}"
    return cache / f"{name}.json", cache / f"{name}.mp4"


def _build(cache: Path) -> None:
    from booth.vision.__main__ import run_clip

    try:
        run_clip(DEMO["seed"], DEMO["period"], DEMO["start"], DEMO["minutes"], cache)
    except Exception as exc:  # surfaced through status()
        log.exception("vision demo build failed")
        _state["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        _state["building"] = False


def status(cache: Path = CACHE, start: bool = True) -> dict:
    """The demo result if ready; otherwise starts building it (once) and reports progress."""
    data_file, _ = paths(cache)
    if data_file.exists():
        return {"status": "ready", **json.loads(data_file.read_text(encoding="utf-8"))}
    reason = available()
    if reason:
        return {"status": "unavailable", "reason": reason}
    with _lock:
        if _state["error"]:
            return {"status": "failed", "reason": _state["error"]}
        if not _state["building"] and start:
            _state["building"] = True
            threading.Thread(target=_build, args=(cache,), daemon=True).start()
    return {"status": "building", "clip": DEMO}
