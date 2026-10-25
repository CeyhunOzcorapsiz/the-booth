"""Render a synthetic broadcast-style video of a match clip (fixed, elevated tactical camera).

The image is deliberately imperfect so the auto-eventing pipeline has real work to do: perspective, grass
stripes, a lighting gradient, overlapping players, shadows, a scoreboard graphic, motion blur on the ball,
sensor noise and video compression. The camera is calibrated only through what is visible: the yellow
corner flags.
"""

from __future__ import annotations

import math

import numpy as np

from booth.sim.match import PITCH_LENGTH, PITCH_WIDTH, Match
from booth.vision.groundtruth import FPS, Frame

W, H = 1280, 720
# Where the four pitch corners land in the image (far side at the top).
IMAGE_CORNERS = np.float32([[255, 170], [1025, 170], [1245, 655], [35, 655]])
WORLD_CORNERS = np.float32([[0, 0], [PITCH_LENGTH, 0], [PITCH_LENGTH, PITCH_WIDTH], [0, PITCH_WIDTH]])
HOME_BGR = (101, 246, 197)
AWAY_BGR = (131, 158, 237)
FLAG_BGR = (0, 215, 255)


def _cv2():
    import cv2

    return cv2


def camera() -> np.ndarray:
    """World (metres) -> image (pixels) homography."""
    return _cv2().getPerspectiveTransform(WORLD_CORNERS, IMAGE_CORNERS)


def project(h: np.ndarray, points) -> np.ndarray:
    pts = np.asarray(points, dtype=np.float32).reshape(-1, 1, 2)
    return _cv2().perspectiveTransform(pts, h).reshape(-1, 2)


def _scale(y_img: float) -> float:
    """Apparent size grows towards the camera."""
    return 0.55 + 0.75 * (y_img - 170) / (655 - 170)


def _pitch_layer(h: np.ndarray) -> np.ndarray:
    cv2 = _cv2()
    img = np.zeros((H, W, 3), np.uint8)
    for row in range(H):  # stadium backdrop with a soft gradient
        img[row, :] = (18 + row // 40, 26 + row // 30, 22 + row // 40)
    stripes = 14
    for i in range(stripes):
        x0, x1 = i * PITCH_LENGTH / stripes, (i + 1) * PITCH_LENGTH / stripes
        quad = project(h, [[x0, 0], [x1, 0], [x1, PITCH_WIDTH], [x0, PITCH_WIDTH]]).astype(np.int32)
        cv2.fillConvexPoly(img, quad, (40, 98, 46) if i % 2 else (36, 88, 42))
    white = (225, 230, 225)

    def line(points, closed=False):
        cv2.polylines(img, [project(h, points).astype(np.int32)], closed, white, 2, cv2.LINE_AA)

    line([[0, 0], [PITCH_LENGTH, 0], [PITCH_LENGTH, PITCH_WIDTH], [0, PITCH_WIDTH]], closed=True)
    line([[52.5, 0], [52.5, PITCH_WIDTH]])
    line(
        [
            [52.5 + 9.15 * math.cos(a / 40 * 2 * math.pi), 34 + 9.15 * math.sin(a / 40 * 2 * math.pi)]
            for a in range(41)
        ]
    )
    for x0, x1 in ((0, 16.5), (PITCH_LENGTH, PITCH_LENGTH - 16.5)):
        line([[x0, 13.84], [x1, 13.84], [x1, 54.16], [x0, 54.16]])
    for x0, x1 in ((0, 5.5), (PITCH_LENGTH, PITCH_LENGTH - 5.5)):
        line([[x0, 24.84], [x1, 24.84], [x1, 43.16], [x0, 43.16]])
    for gx, out in ((0, -1.6), (PITCH_LENGTH, PITCH_LENGTH + 1.6)):  # goals
        line([[gx, 30.34], [out, 30.34], [out, 37.66], [gx, 37.66]])
    for cx, cy in project(h, WORLD_CORNERS):  # corner flags, the only calibration targets
        cv2.circle(img, (int(cx), int(cy) - 9), 6, FLAG_BGR, -1, cv2.LINE_AA)
        cv2.line(img, (int(cx), int(cy)), (int(cx), int(cy) - 9), (200, 200, 200), 1)
    # a little vignetting, like a real lens
    yy, xx = np.mgrid[0:H, 0:W]
    vignette = 1 - 0.18 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    return np.clip(img * vignette[..., None], 0, 255).astype(np.uint8)


def render_frames(match: Match, frames: list[Frame], score_at, seed: int = 0):
    """Yield BGR images for ``frames``. ``score_at(frame)`` returns (minute, home goals, away goals)."""
    cv2 = _cv2()
    h = camera()
    base = _pitch_layer(h)
    rng = np.random.default_rng(seed)
    # a small bank of sensor-noise frames, cycled: realistic grain without killing compression or speed
    noise_bank = [rng.normal(0, 3.5, (H, W, 3)).astype(np.int16) for _ in range(6)]
    numbers = {p.id: p.number for team in match.teams.values() for p in team.players}
    previous_ball = None
    for frame in frames:
        img = base.copy()
        feet = {pid: project(h, [xy])[0] for pid, xy in frame.players.items()}
        for pid, (fx, fy) in sorted(feet.items(), key=lambda kv: kv[1][1]):  # far players first
            s = _scale(fy)
            colour = HOME_BGR if pid.startswith("H") else AWAY_BGR
            cv2.ellipse(
                img, (int(fx + 4 * s), int(fy)), (int(9 * s), int(3 * s)), 0, 0, 360, (24, 52, 28), -1
            )
            top = int(fy - 30 * s)
            cv2.ellipse(
                img,
                (int(fx), int(fy - 15 * s)),
                (int(7 * s), int(15 * s)),
                0,
                0,
                360,
                colour,
                -1,
                cv2.LINE_AA,
            )
            cv2.circle(
                img, (int(fx), top - int(4 * s)), max(int(4.5 * s), 2), (150, 170, 205), -1, cv2.LINE_AA
            )
            cv2.putText(
                img,
                str(numbers.get(pid, "")),
                (int(fx - 5 * s), int(fy - 12 * s)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.3 * s,
                (25, 25, 25),
                1,
                cv2.LINE_AA,
            )
        bx, by = project(h, [frame.ball])[0]
        r = max(int(3.2 * _scale(by)), 2)
        if previous_ball is not None and math.dist(previous_ball, (bx, by)) > 6:  # motion blur
            cv2.line(
                img,
                (int(previous_ball[0]), int(previous_ball[1])),
                (int(bx), int(by)),
                (200, 205, 200),
                r,
                cv2.LINE_AA,
            )
        cv2.circle(img, (int(bx), int(by)), r, (245, 250, 250), -1, cv2.LINE_AA)
        previous_ball = (bx, by)
        minute, home, away = score_at(frame)
        cv2.rectangle(img, (24, 22), (330, 62), (20, 24, 20), -1)
        cv2.putText(
            img,
            f"{match.teams['home'].short} {home}-{away} {match.teams['away'].short}   {minute}",
            (36, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (235, 240, 230),
            2,
            cv2.LINE_AA,
        )
        noisy = img.astype(np.int16)
        noisy += noise_bank[len(noise_bank) and int(frame.t * FPS) % len(noise_bank)]
        img = np.clip(noisy, 0, 255).astype(np.uint8)
        yield cv2.GaussianBlur(img, (3, 3), 0)


def write_video(images, path: str) -> int:
    """Encode BGR images as an H.264 MP4 that browsers can play. Returns the frame count."""
    import imageio.v2 as imageio

    count = 0
    with imageio.get_writer(
        path,
        fps=FPS,
        codec="libx264",
        quality=None,
        pixelformat="yuv420p",
        macro_block_size=8,
        ffmpeg_params=["-crf", "27", "-preset", "veryfast", "-movflags", "+faststart"],
    ) as writer:
        for img in images:
            writer.append_data(img[:, :, ::-1])  # BGR -> RGB
            count += 1
    return count


def read_video(path: str):
    """Yield BGR frames from a video file."""
    import imageio.v2 as imageio

    with imageio.get_reader(path) as reader:
        for rgb in reader:
            yield np.ascontiguousarray(rgb[:, :, ::-1])
