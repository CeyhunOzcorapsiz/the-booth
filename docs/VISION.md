# Video to events (auto-eventing)

The brief suggests "running a model over an incoming video feed to generate the pass and speed metrics automatically, rather than tagging them by hand". We had no real footage (and couldn't use it without rights), so we built the whole loop on **synthetic video we render ourselves**, which also gives us exact ground truth to score against:

```
synthetic match ──▶ tracking (22 players, 1 Hz) ──▶ rendered broadcast clip (MP4)
                                                          │  pixels only
                                                          ▼
                     events + pass distance + ball speed ◀── auto-eventing pipeline
                                                          │
                     score vs. the events the clip was rendered from
```

## The clip (`booth/vision/render.py`)

A fixed, elevated tactical camera at 1280×720, 10 fps: perspective, grass stripes, pitch markings, a lighting vignette, players drawn by depth with shadows and shirt numbers (so they overlap and occlude), the ball with motion blur, a broadcast scoreboard graphic, sensor noise and H.264 compression. The ball is carried at the feet of the player in possession and travels between players at the pass or shot speed recorded on the event (`booth/vision/groundtruth.py`).

## The pipeline (`booth/vision/autoevent.py`)

It reads the encoded MP4 back from disk and knows only the two kit colours and the pitch size (105 × 68 m).

1. **Camera calibration.** Finds the four yellow corner flags, follows each pole down to where the touchlines meet, and fits the image-to-pitch homography from those four points.
2. **Background model.** The per-pixel median of sampled frames; static white pixels (pitch markings) are masked out of ball detection.
3. **Players.** Kit-colour segmentation in Lab space inside the pitch, closed to re-join bodies split by shirt numbers. Round blobs (heads, whose skin tone is close to one kit) and slivers are rejected by shape. The feet are the bottom of the blob, projected to the pitch.
4. **Ball.** Small, bright, low-saturation blobs that moved against the background and aren't part of a player. The candidate that best continues the predicted trajectory wins; after a few lost frames it re-acquires the candidate closest to a player.
5. **Tracking.** Greedy nearest-neighbour tracks per team on the pitch plane.
6. **Possession.** The nearest player within 1.6 m of a slow ball (with hysteresis, so the holder keeps it unless someone is clearly closer). Spells must last 0.3 s; A → B → A flickers under 1 s (duels) are merged.
7. **Events.** A change of possessor within a team is a **pass**, across teams a **turnover**; a fast flight ending at the goal mouth is a **shot**, and the possession change right after it is its outcome, not a turnover. Transfers implying more than 140 km/h are track glitches and dropped. Pass **distance** is measured over the ball's actual flight and **speed** is the median frame-to-frame speed in flight.

## Results

Run it yourself:

```bash
cd backend
pip install -e ".[vision]"
python -m booth.vision --seed 119 --start 76 --minutes 3 --out ../vision-out   # one clip
python -m booth.vision --benchmark --out ../vision-bench                       # six clips, three matches
```

A detection matches a truth event of the same kind and team released within ±1 s; each truth event matches once.

| Event | Truth | Detected | Matched | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| Pass | 139 | 103 | 91 | 0.88 | 0.66 | **0.75** |
| Turnover | 23 | 35 | 18 | 0.51 | 0.78 | 0.62 |
| Shot | 6 | 4 | 3 | 0.75 | 0.50 | 0.60 |

Six 3-minute clips from three matches (seeds 119, 3, 42, both halves), 18 minutes of video:

- **Pass ball speed:** median error 3.4 km/h (mean 8.4)
- **Pass distance:** median error 0.95 m (mean 4.4)
- **Camera calibration** from the corner flags: within 0.2 m on every clip
- Pass F1 per clip ranges from 0.67 to 0.82. The thresholds were tuned on one clip (seed 119, 76'); the other five held up, so the method generalises across matches rather than memorising one.

The web app's **Video to events** tab plays the demo clip with every detection marked as matched, false alarm or missed; click one to jump to it.

## Limits

- The video is synthetic: clean kit colours, a fixed calibrated camera and no crowd, so this is a working pipeline validated end to end, **not** a claim about accuracy on real broadcast footage. Real footage would need a learned detector (e.g. a YOLO-class model) for players and ball, camera tracking for a panning camera, and re-identification across occlusions; the event logic downstream would stay the same.
- Ball height isn't modelled (no lobs or headers in the air); very short passes (under 2 m) aren't counted.
- Occasional ball-track glitches at the start or end of a pass inflate the mean distance error, which is why the median is reported too.
