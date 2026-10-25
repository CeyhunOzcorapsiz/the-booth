# Architecture

## Flow of one broadcast

1. `GET /api/broadcast` creates a `Broadcast` (`backend/booth/orchestrator.py`) for one viewer profile.
2. The **feed** task replays the seeded match (`booth/sim/match.py`) at `speed` match-seconds per second, applies each event to the shared `MatchState` (`booth/state.py`) and streams it to the browser.
3. The **Director** (`booth/agents/director.py`) looks at each event and the viewer's profile and either stays quiet or plans a `Job` with one or more segment kinds: `pbp`, `color`, `stats`, `explain`, `spatial`, `recap`. The job carries a **frozen** copy of the state, so later events can't leak into what the crew says.
4. The **producer** task hands jobs to the `Crew` (`booth/crew.py`). Routine jobs that fall more than 30 match-seconds behind live play are dropped; important ones (goals, red cards, whistles) always air.
5. The crew runs the hand-offs below and emits `trace` messages for each step and `segment` messages for what goes on air.

## The storyline agent

`agents/storyline.py` runs inside `MatchState.apply`, so it sees every event in order and keeps memory across the whole match. It records storylines (comeback, turnaround, late equalizer or winner, brace or hat-trick, quick-fire goals, a goal against the run of play, down to ten) with the numbers behind them. When a storyline starts:

- the director raises the moment's importance and always schedules the analyst;
- the crew adds the storylines to the fact sheet, so model writers can use them and the fact-checker accepts their numbers;
- templates and recaps lead with the most important storyline.

The stats desk also exposes `storylines` as a tool for the model-backed stats producer.

## Hand-offs inside the crew

```
Stats producer ──facts──▶ Writer ──draft──▶ Fact-checker ──approved──▶ Localizer ──▶ on air
                              ▲                  │
                              └──reasons─────────┘  (one rewrite)
                    any failure ──▶ template for that segment (labelled)
```

- **Stats producer** (`agents/stats_producer.py`) gives the model the `StatsDesk` methods as Agent Framework function tools: `score`, `team_stats`, `compare`, `player_stats`, `momentum`, `key_moments`. Each call registers `Fact`s with stable IDs on a `FactSheet`. If the model fails or fetches too little, a rule-based selection fills the sheet.
- **Writers** (`agents/writers.py`) produce an English world-feed line. The prompt contains only the moment, the score, the clubs, a location description and (for the analyst and recap) the fact sheet.
- **Fact-checker** (`agents/fact_checker.py`):
  - every number must match the event, the score, the minute, a shirt number of a player involved, or a fact on the sheet (±0.5 for rounding);
  - every named player must be involved in the moment or appear in the facts;
  - length limits per segment kind;
  - for analyst and recap lines, a model review for unsupported claims (intent, injuries, history).
- **Localizer** (`agents/localizer.py`) translates the world feed. The translation is refused if its numbers differ from the source.
- **Templates** (`agents/templates.py`) cover English and Turkish and are built only from the same data, so they pass the same checks.

## Model runtime

`booth/llm.py` wraps Microsoft Agent Framework's `OpenAIChatCompletionClient` for any OpenAI v1-compatible endpoint (Microsoft Foundry, GitHub Models). Each agent turn is an `agent_framework.Agent` with its own instructions and tools. Around every call:

- concurrency limit (`BOOTH_LLM_CONCURRENCY`),
- timeout (`BOOTH_LLM_TIMEOUT`),
- importance budget (`BOOTH_LLM_MIN_IMPORTANCE`): routine moments never call a model,
- circuit breaker: after repeated failures the crew runs on templates for a cooldown, and the UI badge says so.

## Shared state and caching

- `MatchState` is the single source of truth: score, per-team and per-player counters, possession time, a five-minute momentum window and key moments.
- `Crew` caches finished segments per `(seed, event, kind, profile)`, so viewers with the same profile share work.

## Roadmap

- Azure AI Speech voices (free tier) for the audio-first mode.
- Run agents as Foundry Agent Service agents and add Foundry evaluations for the fact-checker.
- Azure Container Apps deployment with Application Insights tracing of every agent hand-off.
- Multi-viewer "same moment, three broadcasts" comparison view for the demo.
