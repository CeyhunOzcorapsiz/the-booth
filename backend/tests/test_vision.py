"""Auto-eventing on synthetic video. Needs the vision extra (OpenCV, ffmpeg); skipped otherwise."""

import pytest

pytest.importorskip("cv2")
pytest.importorskip("imageio_ffmpeg")

from booth.sim import generate_match  # noqa: E402
from booth.sim.tracking import tracking_for  # noqa: E402
from booth.vision.__main__ import run_clip  # noqa: E402
from booth.vision.autoevent import calibrate  # noqa: E402
from booth.vision.groundtruth import build  # noqa: E402
from booth.vision.render import render_frames  # noqa: E402


def test_ground_truth_ball_follows_the_play():
    match = generate_match(119)
    frames, truth = build(match, tracking_for(match), 2, 76 * 60, 77 * 60)
    assert len(frames) == 600 and all(0 <= f.ball[0] <= 107 and 0 <= f.ball[1] <= 68 for f in frames)
    assert {e.kind for e in truth} >= {"pass"}
    assert all(e.speed_kmh < 140 for e in truth)


def test_camera_is_calibrated_from_the_corner_flags_alone():
    match = generate_match(119)
    frames, _ = build(match, tracking_for(match), 2, 76 * 60, 76 * 60 + 1)
    image = next(render_frames(match, frames, lambda f: ("76'", 0, 2)))
    h, corners = calibrate(image)
    assert len(corners) == 4
    import numpy as np

    from booth.vision.autoevent import to_world
    from booth.vision.render import camera, project

    centre = project(camera(), [[52.5, 34.0]])
    assert np.linalg.norm(to_world(h, centre)[0] - [52.5, 34.0]) < 0.5


def test_auto_eventing_recovers_passes_from_pixels(tmp_path):
    run = run_clip(119, 2, 76, 1.5, tmp_path)
    report = run["report"]
    assert (tmp_path / run["clip"]["video"]).stat().st_size > 50_000
    assert report["calibration_error_m"] < 0.5
    assert 18 <= run["pipeline"]["mean_players_detected"] <= 26
    passes = report["events"]["pass"]
    assert passes["truth"] >= 5
    assert passes["recall"] >= 0.5 and passes["precision"] >= 0.5
    assert report["pass_speed_mae_kmh"] is not None and report["pass_speed_mae_kmh"] < 15
