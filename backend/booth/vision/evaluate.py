"""Score auto-eventing against the ground truth the clip was rendered from.

A detection matches a truth event of the same kind and team whose release time is within ``TOLERANCE_S``.
Each truth event can be matched once. Reports precision, recall and F1 per kind, pass distance and ball
speed errors on matched passes, and the calibration error of the fitted homography.
"""

from __future__ import annotations

import statistics

import numpy as np

from booth.vision.autoevent import Detection, to_world
from booth.vision.groundtruth import TruthEvent
from booth.vision.render import IMAGE_CORNERS, camera

TOLERANCE_S = 1.0
KINDS = ("pass", "turnover", "shot")


def match(detections: list[Detection], truth: list[TruthEvent], clip_start: float):
    pairs, used = [], set()
    for d in detections:
        best = None
        for j, t in enumerate(truth):
            if j in used or t.kind != d.kind or t.team != d.team:
                continue
            gap = abs((t.t - clip_start) - d.t)
            if gap <= TOLERANCE_S and (best is None or gap < best[0]):
                best = (gap, j)
        if best:
            used.add(best[1])
            pairs.append((d, truth[best[1]]))
    return pairs


def report(detections: list[Detection], truth: list[TruthEvent], clip_start: float, homography) -> dict:
    pairs = match(detections, truth, clip_start)
    by_kind = {}
    for kind in KINDS:
        tp = sum(1 for d, _ in pairs if d.kind == kind)
        n_det = sum(1 for d in detections if d.kind == kind)
        n_true = sum(1 for t in truth if t.kind == kind)
        precision = tp / n_det if n_det else None
        recall = tp / n_true if n_true else None
        f1 = (2 * precision * recall / (precision + recall)) if precision and recall else None
        by_kind[kind] = {
            "truth": n_true,
            "detected": n_det,
            "matched": tp,
            "precision": None if precision is None else round(precision, 3),
            "recall": None if recall is None else round(recall, 3),
            "f1": None if f1 is None else round(f1, 3),
        }
    passes = [(d, t) for d, t in pairs if d.kind == "pass"]
    speed_err = [abs(d.speed_kmh - t.speed_kmh) for d, t in passes]
    dist_err = [abs(d.distance_m - t.distance_m) for d, t in passes]
    timing = [abs(d.t - (t.t - clip_start)) for d, t in pairs]
    # calibration: where the fitted homography puts the true corner pixels, in metres
    h = np.asarray(homography, dtype=np.float32)
    true_world = to_world(np.linalg.inv(camera()).astype(np.float32), IMAGE_CORNERS)
    fitted_world = to_world(h, IMAGE_CORNERS)
    calib = float(np.mean(np.linalg.norm(true_world - fitted_world, axis=1)))
    return {
        "events": by_kind,
        "pass_speed_mae_kmh": round(statistics.mean(speed_err), 1) if speed_err else None,
        "pass_distance_mae_m": round(statistics.mean(dist_err), 2) if dist_err else None,
        "pass_speed_median_error_kmh": round(statistics.median(speed_err), 1) if speed_err else None,
        "pass_distance_median_error_m": round(statistics.median(dist_err), 2) if dist_err else None,
        "timing_mae_s": round(statistics.mean(timing), 2) if timing else None,
        "calibration_error_m": round(calib, 2),
        "tolerance_s": TOLERANCE_S,
    }
