# Overlay cues

The Booth emits timed, machine-readable cues that a broadcast graphics engine can render in sync with the match: a score bug, lower thirds, stat cards, player tags and storyline banners. Every cue is built from the shared match state and lists the event and fact ids behind it, so on-screen graphics are as verifiable as the commentary.

## Where to get them

| Source | Use |
|---|---|
| `GET /api/overlays?seed=119&lang=en&from_minute=0&to_minute=130` | All cues for a match (or a time window) as JSON |
| `GET /api/broadcast?...` | Live: `overlay` server-sent events (`{"type": "overlay", "cue": {...}}`), interleaved with the broadcast |
| MCP tool `overlay_cues` | For other agents |

Labels follow `lang` (`en`, `tr`; other languages fall back to English).

## Cue

```json
{
  "id": "C0060",
  "at": {"period": 2, "clock_s": 5363.2, "display_minute": "90'"},
  "duration_s": 8,
  "type": "lower_third",
  "priority": 3,
  "payload": {"title": "GOAL", "player": {"id": "H10", "name": "Kerem Navarro", "number": 10, "team": "Northstar FC"},
              "lines": [], "team": "Northstar FC"},
  "evidence": ["E0995"]
}
```

| Field | Meaning |
|---|---|
| `at` | Match position: half, seconds since kick-off (second half starts at 2700) and the broadcast minute |
| `duration_s` | Suggested on-screen time in match seconds (0 = persistent until replaced, e.g. the score bug) |
| `priority` | 1 = ambient, 2 = notable, 3 = must show. Lower priorities can be dropped when the screen is busy |
| `evidence` | Event ids (`E…`), storyline ids (`S…`) and fact ids (`F…`) the cue was built from |

## Types

| `type` | When | `payload` |
|---|---|---|
| `score_bug` | Kick-offs, goals, half and full time | `home`, `away` (short names), `home_goals`, `away_goals`, `minute` |
| `lower_third` | Goals, cards, penalties, substitutions | `title`, `player` (id, name, number, team), `lines` (assist, on/off), `team` |
| `stat_card` | Every 15 minutes, half time, full time | `title`, `home`, `away`, `rows` of `{label, home, away}` (possession, shots, on target, pass accuracy) |
| `player_tag` | Thresholds: shot ≥ 100 km/h, pass difficulty ≥ 80/100, pass ≥ 45 m | `player`, `metric`, `value`, `label`, `x`, `y` (pitch metres) |
| `storyline_banner` | When the storyline agent finds a narrative | `title`, `kind`, `text` |

The web app previews lower thirds, stat cards and player tags on its pitch from the same cues.
