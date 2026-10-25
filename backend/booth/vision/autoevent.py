"""Auto-eventing: turn match video into events, using only what is in the pixels.

The pipeline sees the frames, the two kit colours and the pitch dimensions. It never reads the simulator.

1. **Calibration** – find the four corner flags, follow each pole down to where the touchlines meet, and fit
   the image-to-pitch homography from those four points.
2. **Background model** – the per-pixel median of sampled frames removes static pitch markings.
3. **Detection** – players by kit colour (blobs inside the pitch, feet at the blob's bottom); the ball as a
   small, bright, moving blob that is not part of a player.
4. **Tracking** – greedy nearest-neighbour tracks per team on the pitch plane; the ball is the candidate
   that best continues its trajectory.
5. **Events** – possession is the nearest player within reach of a slow ball. A change of possessor within a
   team is a pass, across teams a turnover; a fast flight ending at the goal mouth is a shot. Pass distance
   and ball speed are measured from the ball's path between release and reception.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import numpy as np

from booth.sim.match import PITCH_LENGTH, PITCH_WIDTH
from booth.vision.render import AWAY_BGR, HOME_BGR, WORLD_CORNERS

REACH_M = 1.6  # a player controls the ball within this distance
CONTROL_MAX_KMH = 28  # faster than this the ball is in flight
MIN_PASS_M = 2.0
HOLD_FRAMES = 3  # 0.3 s of control starts a possession spell
FLICKER_S = 1.0
MAX_BALL_KMH = 140
OWNER_MARGIN_M = 0.6
SHOT_FOLLOW_UP_S = 2.5
BALL_GATE_M = 4.5  # about 45 m/s at 10 fps
REACQUIRE_AFTER = 3  # frames without a plausible candidate
SHOT_MIN_KMH = 40
SHOT_MAX_RANGE_M = 35
SHOT_MIN_GAIN_M = 5
TRACK_GATE_M = 2.6


def _cv2():
    import cv2

    return cv2


@dataclass
class Detection:
    kind: str  # pass | turnover | shot
    t: float  # seconds from the start of the clip, when the ball left the player
    team: str
    end_t: float
    start: tuple[float, float]
    end: tuple[float, float]
    distance_m: float
    speed_kmh: float

    def to_dict(self) -> dict:
        data = asdict(self)
        data["start"] = [round(v, 2) for v in self.start]
        data["end"] = [round(v, 2) for v in self.end]
        return data


@dataclass
class Result:
    fps: int
    homography: list
    flags_px: list
    detections: list[Detection]
    ball: list  # per frame [x, y] in metres, or None
    players_per_frame: list[int]
    stats: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "fps": self.fps,
            "homography": self.homography,
            "flags_px": self.flags_px,
            "detections": [d.to_dict() for d in self.detections],
            "ball": self.ball,
            "players_per_frame": self.players_per_frame,
            "stats": self.stats,
        }


# --- 1. calibration -------------------------------------------------------------------------------------
def calibrate(frame: np.ndarray) -> tuple[np.ndarray, list]:
    """Image -> pitch homography from the corner flags. Returns (H, corner pixels)."""
    cv2 = _cv2()
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    yellow = cv2.inRange(hsv, (18, 120, 150), (38, 255, 255))
    count, _, stats, centroids = cv2.connectedComponentsWithStats(yellow)
    blobs = sorted(range(1, count), key=lambda i: -stats[i, cv2.CC_STAT_AREA])[:4]
    if len(blobs) < 4:
        raise RuntimeError("calibration failed: fewer than four corner flags visible")
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners = []
    for i in blobs:
        cx, cy = centroids[i]
        x, y = int(round(cx)), int(stats[i, cv2.CC_STAT_TOP] + stats[i, cv2.CC_STAT_HEIGHT])
        # follow the pole down to the first bright pitch-line pixel: that is where the touchlines meet
        for dy in range(0, 30):
            if gray[min(y + dy, gray.shape[0] - 1), x] > 185:
                y = y + dy
                break
        corners.append((float(x), float(y)))
    top = sorted(sorted(corners, key=lambda p: p[1])[:2])
    bottom = sorted(sorted(corners, key=lambda p: p[1])[2:])
    ordered = np.float32([top[0], top[1], bottom[1], bottom[0]])
    return cv2.getPerspectiveTransform(ordered, WORLD_CORNERS), ordered.tolist()


def to_world(h: np.ndarray, points) -> np.ndarray:
    if len(points) == 0:
        return np.zeros((0, 2), np.float32)
    pts = np.asarray(points, dtype=np.float32).reshape(-1, 1, 2)
    return _cv2().perspectiveTransform(pts, h).reshape(-1, 2)


# --- 3. detection ---------------------------------------------------------------------------------------
def _kit_mask(lab: np.ndarray, ref_img: np.ndarray, threshold: int = 42) -> np.ndarray:
    """Pixels within an L1 distance of the kit colour in Lab space."""
    cv2 = _cv2()
    diff = cv2.absdiff(lab, ref_img)
    dist = cv2.add(cv2.add(diff[:, :, 0] // 2, diff[:, :, 1]), diff[:, :, 2])  # lightness counts half
    return (dist < threshold).astype(np.uint8) * 255


def _players(lab: np.ndarray, pitch_mask: np.ndarray, h: np.ndarray, refs: dict):
    """Player feet on the pitch plane per team, plus the team masks.

    Bodies are tall blobs; round blobs (heads, whose skin tone is close to the coral kit) and slivers are
    dropped, and blobs split by a shirt number are closed up first.
    """
    cv2 = _cv2()
    out = {}
    close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 5))
    for team, ref_img in refs.items():
        mask = cv2.morphologyEx(_kit_mask(lab, ref_img) & pitch_mask, cv2.MORPH_CLOSE, close)
        count, _, stats, _ = cv2.connectedComponentsWithStats(mask)
        feet = []
        for i in range(1, count):
            area = stats[i, cv2.CC_STAT_AREA]
            w, hgt = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
            if area < 14 or hgt < 1.35 * w:
                continue
            x = stats[i, cv2.CC_STAT_LEFT] + w / 2
            y = stats[i, cv2.CC_STAT_TOP] + hgt
            feet.append((x, y))
        out[team] = (to_world(h, feet), mask)
    return out


def _line_mask(background: np.ndarray) -> np.ndarray:
    """Static white pixels (pitch markings) in the background, slightly dilated."""
    cv2 = _cv2()
    hsv = cv2.cvtColor(background, cv2.COLOR_BGR2HSV)
    lines = ((hsv[:, :, 2] > 165) & (hsv[:, :, 1] < 60)).astype(np.uint8) * 255
    return cv2.dilate(lines, np.ones((5, 5), np.uint8))


def _ball_candidates(
    frame: np.ndarray,
    background: np.ndarray,
    players_mask: np.ndarray,
    pitch_mask: np.ndarray,
    line_mask: np.ndarray,
):
    """Small bright moving blobs that are neither part of a player nor a pitch marking."""
    cv2 = _cv2()
    moving = cv2.cvtColor(cv2.absdiff(frame, background), cv2.COLOR_BGR2GRAY) > 15
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    white = (hsv[:, :, 2] > 175) & (hsv[:, :, 1] < 50)
    mask = (moving & white & (players_mask == 0) & (pitch_mask > 0) & (line_mask == 0)).astype(np.uint8) * 255
    count, _, stats, centroids = cv2.connectedComponentsWithStats(mask)
    return [tuple(centroids[i]) for i in range(1, count) if 2 <= stats[i, cv2.CC_STAT_AREA] <= 120]


# --- 4. tracking ----------------------------------------------------------------------------------------
class _Tracks:
    def __init__(self):
        self.next_id = 0
        self.tracks: dict[int, tuple[np.ndarray, int]] = {}  # id -> (position, frames since seen)

    def update(self, points: np.ndarray) -> list[tuple[int, np.ndarray]]:
        assigned: list[tuple[int, np.ndarray]] = []
        free = set(self.tracks)
        pairs = sorted(
            ((float(np.linalg.norm(p - self.tracks[t][0])), i, t) for i, p in enumerate(points) for t in free)
        )
        used_points, used_tracks = set(), set()
        for dist, i, t in pairs:
            if dist > TRACK_GATE_M or i in used_points or t in used_tracks:
                continue
            used_points.add(i)
            used_tracks.add(t)
            self.tracks[t] = (points[i], 0)
            assigned.append((t, points[i]))
        for i, p in enumerate(points):
            if i not in used_points:
                self.tracks[self.next_id] = (p, 0)
                assigned.append((self.next_id, p))
                self.next_id += 1
        for t in list(self.tracks):
            if t not in used_tracks and all(t != a for a, _ in assigned):
                pos, missed = self.tracks[t]
                if missed > 10:
                    del self.tracks[t]
                else:
                    self.tracks[t] = (pos, missed + 1)
        return assigned


# --- pipeline ---------------------------------------------------------------------------------------------
def analyse(frames: list[np.ndarray], fps: int) -> Result:
    cv2 = _cv2()
    if not frames:
        raise ValueError("no frames")
    h, flags = calibrate(frames[0])
    sample = frames[:: max(len(frames) // 25, 1)][:25]
    background = np.median(np.stack(sample), axis=0).astype(np.uint8)
    pitch_poly = np.int32(flags)
    pitch_mask = np.zeros(frames[0].shape[:2], np.uint8)
    cv2.fillConvexPoly(pitch_mask, pitch_poly, 255)
    line_mask = _line_mask(background)

    shape = frames[0].shape
    refs = {
        team: np.full(shape, cv2.cvtColor(np.uint8([[bgr]]), cv2.COLOR_BGR2LAB)[0, 0], np.uint8)
        for team, bgr in (("home", HOME_BGR), ("away", AWAY_BGR))
    }
    tracks = {"home": _Tracks(), "away": _Tracks()}
    ball_world: list = []
    control: list = []  # per frame (team, track id) or None
    current_owner = None
    counts = []
    last_ball = None
    velocity = np.zeros(2, np.float32)
    lost = 0
    for frame in frames:
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        found = _players(lab, pitch_mask, h, refs)
        players_mask = cv2.dilate(found["home"][1] | found["away"][1], np.ones((5, 5), np.uint8))
        people = {team: tracks[team].update(found[team][0]) for team in tracks}
        counts.append(sum(len(v) for v in people.values()))
        candidates = to_world(h, _ball_candidates(frame, background, players_mask, pitch_mask, line_mask))
        ball = None
        everyone = [p for team in people for _, p in people[team]]
        if len(candidates):
            if last_ball is not None and lost < REACQUIRE_AFTER:
                predicted = last_ball + velocity
                dists = np.linalg.norm(candidates - predicted, axis=1)
                best = int(np.argmin(dists))
                if dists[best] <= BALL_GATE_M:
                    ball = candidates[best]
            if ball is None and (last_ball is None or lost >= REACQUIRE_AFTER) and everyone:
                # (re)acquire: the ball is almost always close to a player
                near = [float(np.min(np.linalg.norm(np.asarray(everyone) - c, axis=1))) for c in candidates]
                best = int(np.argmin(near))
                if near[best] <= 3.0:
                    ball = candidates[best]
        lost = 0 if ball is not None else lost + 1
        if ball is not None and last_ball is not None:
            velocity = 0.6 * velocity + 0.4 * (ball - last_ball)
        if ball is None and last_ball is not None:
            # occluded or merged with a player: the nearest player's feet are the best guess
            near = [(float(np.linalg.norm(p - last_ball)), p) for team in people for _, p in people[team]]
            near = [n for n in near if n[0] <= REACH_M * 1.5]
            ball = min(near, key=lambda n: n[0])[1] if near else last_ball
        ball_world.append(None if ball is None else (float(ball[0]), float(ball[1])))
        speed = 0.0
        if ball is not None and last_ball is not None:
            speed = float(np.linalg.norm(ball - last_ball)) * fps * 3.6
        last_ball = ball
        owner = None
        if ball is not None and speed < CONTROL_MAX_KMH:
            reach = {}
            for team, assigned in people.items():
                for tid, p in assigned:
                    d = float(np.linalg.norm(p - ball))
                    if d <= REACH_M:
                        reach[(team, tid)] = d
            if reach:
                nearest = min(reach, key=reach.get)
                # hysteresis: whoever has the ball keeps it while still in reach, unless someone is clearly closer
                keep = current_owner in reach and reach[current_owner] <= reach[nearest] + OWNER_MARGIN_M
                owner = current_owner if keep else nearest
        current_owner = owner or current_owner
        control.append(owner)

    detections = _events(control, ball_world, fps)
    observed = [b for b in ball_world if b is not None]
    return Result(
        fps=fps,
        homography=h.tolist(),
        flags_px=flags,
        detections=detections,
        ball=[None if b is None else [round(b[0], 2), round(b[1], 2)] for b in ball_world],
        players_per_frame=counts,
        stats={
            "frames": len(frames),
            "ball_seen_pct": round(100 * len(observed) / len(ball_world), 1),
            "mean_players_detected": round(float(np.mean(counts)), 1),
        },
    )


def _possession_spells(control: list, fps: int) -> list[tuple[tuple, int, int]]:
    """(owner, first frame, last frame) spells, robust to flicker.

    An owner must hold the ball for HOLD_FRAMES in a row to start a spell; spells of the same owner separated
    by short gaps are joined, and a brief spell squeezed between two spells of one owner (A -> B -> A within
    FLICKER_S, typical of a duel) is dropped.
    """
    spells: list[list] = []
    run_owner, run_start = None, 0
    for i, owner in enumerate(control + [None]):
        if owner != run_owner:
            if run_owner is not None and i - run_start >= HOLD_FRAMES:
                if spells and spells[-1][0] == run_owner:
                    spells[-1][2] = i - 1
                else:
                    spells.append([run_owner, run_start, i - 1])
            run_owner, run_start = owner, i
    cleaned: list[list] = []
    for spell in spells:
        if (
            len(cleaned) >= 2
            and cleaned[-2][0] == spell[0]
            and (cleaned[-1][2] - cleaned[-1][1] + 1) / fps < FLICKER_S
        ):
            cleaned.pop()
            cleaned[-1][2] = spell[2]
        elif cleaned and cleaned[-1][0] == spell[0]:
            cleaned[-1][2] = spell[2]
        else:
            cleaned.append(spell)
    return [(o, a, b) for o, a, b in cleaned]


def _flight_window(ball: list, a: int, b: int, fps: int) -> tuple[int, int]:
    """Frames where the ball actually travels between release ``a`` and reception ``b``.

    The pass is measured from the last slow frame before the ball speeds up to the first slow frame after it
    stops travelling, so the roll into the receiver's feet doesn't inflate the distance.
    """

    def fast(i: int) -> bool:
        return (
            ball[i] is not None
            and ball[i + 1] is not None
            and CONTROL_MAX_KMH < math.dist(ball[i], ball[i + 1]) * fps * 3.6 <= MAX_BALL_KMH
        )

    moving = [i for i in range(a, b) if fast(i)]
    if not moving:
        return a, b
    return moving[0], min(moving[-1] + 1, b)


def _flight_speed(ball: list, a: int, b: int, fps: int) -> float | None:
    """Median frame-to-frame ball speed while it travels (km/h); None if the flight is too short."""
    speeds = [
        math.dist(ball[i], ball[i + 1]) * fps * 3.6
        for i in range(a, b)
        if ball[i] is not None and ball[i + 1] is not None
    ]
    fast = [v for v in speeds if CONTROL_MAX_KMH < v <= MAX_BALL_KMH]
    return round(sorted(fast)[len(fast) // 2], 1) if len(fast) >= 2 else None


def _events(control: list, ball: list, fps: int) -> list[Detection]:
    """Possession changes -> passes and turnovers; fast flights into the goal mouth -> shots."""
    detections: list[Detection] = []
    spells = _possession_spells(control, fps)
    for (owner_a, _, release), (owner_b, receive, _) in zip(spells, spells[1:], strict=False):
        if ball[release] is None or ball[receive] is None:
            continue
        if (
            math.dist(ball[release], ball[receive]) / max((receive - release) / fps, 1 / fps) * 3.6
            > MAX_BALL_KMH
        ):
            continue  # the ball track jumped: not a real transfer
        first, last = _flight_window(ball, release, receive, fps)
        start, end = ball[first], ball[last]
        distance = math.dist(start, end)
        duration = max((receive - release) / fps, 1 / fps)
        speed = _flight_speed(ball, release, receive, fps) or distance / duration * 3.6
        if owner_b[0] == owner_a[0]:
            if owner_b[1] != owner_a[1] and distance >= MIN_PASS_M:
                detections.append(
                    Detection(
                        "pass",
                        release / fps,
                        owner_b[0],
                        receive / fps,
                        start,
                        end,
                        round(distance, 1),
                        round(speed, 1),
                    )
                )
        else:
            detections.append(
                Detection(
                    "turnover",
                    release / fps,
                    owner_b[0],
                    receive / fps,
                    start,
                    end,
                    round(distance, 1),
                    round(speed, 1),
                )
            )
    stable = [None] * len(control)
    for owner, a, b in spells:
        for i in range(a, b + 1):
            stable[i] = owner
    shots = _shots(ball, stable, fps)
    # the possession change right after a shot is its outcome (save, goal, goal kick), not a turnover
    detections = [
        d
        for d in detections
        if not (d.kind == "turnover" and any(0 <= d.t - s.t <= SHOT_FOLLOW_UP_S for s in shots))
    ]
    return sorted(detections + shots, key=lambda d: d.t)


def _shots(ball: list, stable: list, fps: int) -> list[Detection]:
    shots = []
    i = 1
    while i < len(ball):
        if ball[i] is None or ball[i - 1] is None:
            i += 1
            continue
        speed = math.dist(ball[i], ball[i - 1]) * fps * 3.6
        if speed < SHOT_MIN_KMH:  # look for the start of a fast flight
            i += 1
            continue
        j = i
        while (
            j + 1 < len(ball) and ball[j + 1] is not None and math.dist(ball[j + 1], ball[j]) * fps * 3.6 > 15
        ):
            j += 1
        end = ball[j]
        if math.dist(ball[i - 1], end) / max((j - i + 1) / fps, 1 / fps) * 3.6 > MAX_BALL_KMH:
            i = j + 1
            continue  # a jump of the track (e.g. the ball placed back on the centre spot)
        goal_x = 0 if end[0] < PITCH_LENGTH / 2 else PITCH_LENGTH
        start = ball[i - 1]
        gained = abs(start[0] - goal_x) - abs(end[0] - goal_x)  # metres travelled towards the goal line
        flight = _flight_speed(ball, i - 1, j, fps) or 0.0
        is_shot = (
            abs(end[0] - goal_x) <= 4
            and 24 <= end[1] <= PITCH_WIDTH - 24
            and abs(start[0] - goal_x) <= SHOT_MAX_RANGE_M
            and gained >= SHOT_MIN_GAIN_M
            and flight >= SHOT_MIN_KMH
        )
        if is_shot:
            team = "home" if goal_x == PITCH_LENGTH else "away"
            distance = math.dist(start, end)
            shots.append(
                Detection(
                    "shot",
                    (i - 1) / fps,
                    team,
                    j / fps,
                    start,
                    end,
                    round(distance, 1),
                    round(distance / max((j - i + 1) / fps, 1 / fps) * 3.6, 1),
                )
            )
        i = j + 1
    return shots
