# Synthetic dataset

The Booth's match generator doubles as a dataset generator, for analytics (Microsoft Fabric, Power BI, pandas) or for training and evaluating other football AI. Every club, player and event is fictional and generated from a seed, so the data can be shared freely.

```bash
cd backend
python -m booth.dataset --matches 200 --first-seed 1 --out ../synthetic-data
```

Roughly 1,000 events per match (about 0.5 MB of CSV per match). Seeds are deterministic: the same seed always gives the same match.

## Tables

All tables join on `match_id` (`M000119` for seed 119) and `player_id` (`H9` = home shirt 9, `A4` = away shirt 4).

### `matches.csv`, one row per match

`match_id, seed, home, away, home_goals, away_goals, home_shots, away_shots, home_on_target, away_on_target, home_possession_pct, away_possession_pct, home_corners, away_corners, home_fouls, away_fouls, home_cards, away_cards, events, storylines` (semicolon-separated storyline kinds)

### `events.csv`, one row per event (`events.jsonl` has the same rows plus the nested `detail` object)

| Column | Meaning |
|---|---|
| `period`, `clock_s`, `minute`, `display_minute` | Half (1/2), seconds since kick-off (second half starts at 2700), minute, broadcast minute such as `45+2'` |
| `type` | `kickoff, pass, tackle, interception, foul, free_kick, penalty_awarded, shot, goal, corner, offside, yellow_card, red_card, substitution, stoppage_time, half_time, full_time` |
| `team`, `player_id`, `target_id` | Acting team and player; target is the receiver, the fouled player, the assist provider (on goals) or the player substituted off |
| `x`, `y`, `end_x`, `end_y` | Metres on a 105 × 68 pitch; home always attacks towards x = 105 |
| `outcome` | Passes: `complete` or `intercepted`; shots: `goal, saved, blocked, off_target` |
| `possession`, `phase` | Team in possession after the event; possession-phase counter |
| `distance_m`, `chance_quality`, `body_part`, `situation` | Shots only. `chance_quality` is a synthetic number from distance and angle, **not** an xG model |
| `pass_distance_m`, `progressive_m`, `difficulty` | Passes only. Distance, metres gained towards goal, and a 0-100 difficulty rating (longer, more forward, into the final third or box, switches of play are harder) |
| `ball_speed_kmh` | Passes and shots. Synthetic speed estimate (what a tracking provider would supply) |

### `players.csv`, one row per player per match

Squad info (`number, name, position, starter`), per-match counters (`passes, shots, shots_on_target, goals, assists, tackles, interceptions, fouls, saves, yellow_cards, red_cards`) and running stats from tracking (`distance_km, top_speed_kmh, sprints, high_intensity_m`).

### `tracking.csv` (with `--tracking`)

1 Hz synthetic tracking: `match_id, period, clock_s, player_id, x, y, speed_kmh`, about 125,000 rows (4.5 MB) per match. Built to be consistent with the events (players involved in an event are at the ball) and calibrated to look like football: about 10-11 km per outfield player, top speeds of 29-34 km/h, 15-40 sprints (two seconds or more above 25 km/h).

### `storylines.csv`

Narratives found by the storyline agent: `kind` is one of `comeback, turnaround, late_equalizer, late_winner, brace, hat_trick, quick_fire, against_the_run, down_to_ten`, with English and Turkish text (`text_en`, `text_tr`); the live state carries all 12 languages in `texts`.

## Loading into Microsoft Fabric

Upload the CSV files to a Lakehouse (**Files → Upload**), then **Load to Tables** for each file. The four tables form a star schema with `matches` and `players` as dimensions.

## Limits

The generator is a possession-phase model tuned so that averages look like football (about 2.7 goals and 32 shots per match). It is not calibrated against real data and has no off-ball tracking. Don't use it to draw conclusions about real football.
