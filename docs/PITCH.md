# Project pitch

## One line

**The Booth is an AI broadcast crew that gives every fan their own live football broadcast, in their language and style, and fact-checks every line before it goes on air.**

## Elevator pitch (for the submission form)

A live match is made by a crew (director, commentator, analyst, stats producer, translator), but that crew makes one show, in one language, for everyone. Fans who speak another language, people new to the game and blind or low-vision fans are left with a broadcast that wasn't made for them.

The Booth replays synthetic, football-realistic match events and runs a multi-agent crew per viewer. A director agent decides what matters to *this* viewer. A storyline agent remembers the whole match, so the crew can say "they were two down and have fought back" instead of just "goal". A stats producer pulls context through tool calls on a shared match state. Play-by-play, analyst and recap agents write the broadcast. A fact-checker blocks any number or name it can't trace to the data and hands rejected drafts back for a rewrite. A localizer adapts the feed into the viewer's language and is refused if a number changes. An audio-first mode describes where the ball is on the pitch and reads everything aloud. Fans can pick a favorite club and a player to follow. Synthetic tracking of all 22 players adds distance covered, top speeds and sprints. Pass difficulty, pass accuracy, shot speed and a control-vs-chaos rhythm meter explain how the game is being played, and every graphic is emitted as a timed overlay cue a broadcaster's graphics engine can render.

The result is one match, many broadcasts: a hype call in English, a calm Turkish explainer for a newcomer and a tactical breakdown, all from the same moment and all verified. The control room shows every hand-off live, and the crew degrades gracefully: on a timeout, quota error or rejected draft it falls back to labelled templates, so the show never stops.

## Microsoft and GitHub technology

- **Microsoft Agent Framework**: every model-backed agent (stats producer, play-by-play, analyst, recap editor, fact-checker review, localizer, studio analyst) is an Agent Framework `Agent`; the stats desk is exposed as function tools; the writer ⇄ fact-checker → localizer hand-off is an Agent Framework workflow with a typed reject-and-rewrite loop; built-in OpenTelemetry instrumentation. The director, storyline tracker and guide are deliberately rule-based: fast, cheap and explainable on every event.
- **Microsoft Foundry**: `gpt-4.1-mini` deployment behind all model-backed agents.
- **Model Context Protocol**: the stats desk and crew as an MCP server, so GitHub Copilot or other agents can query matches and request fact-checked commentary.
- **Video to events**: a computer-vision pipeline (OpenCV) that turns rendered match video into passes, turnovers and shots with pass speed and distance, benchmarked against ground truth (pass F1 0.75, median speed error 3.4 km/h).
- **Synthetic dataset export**: matches, events, players and storylines as CSV/JSONL for Microsoft Fabric.
- **Azure Container Apps**: hosting, scale to zero.
- **Azure Monitor / Application Insights**: a trace for every director job, agent run, model call and tool call.
- **GitHub**: Actions CI (tests, lint, container build), GitHub Container Registry, GitHub Copilot during development.

## What problem it solves

- **Personalisation at broadcast scale:** one crew serves every language and level. The English world feed is shared and only the localization is per language, with segments cached per profile, so cost grows with the number of profiles, not viewers.
- **Accessibility:** an audio-first broadcast for blind and low-vision fans, with spatial descriptions, which a human crew can't produce for every match.
- **Trust:** an AI commentator that can't invent a statistic, which is what broadcasters need before putting generated text on air.

## Categories

Primary: **Best Multi-Agent Orchestration**. Specialised agents with distinct roles, shared frozen state, explicit hand-offs (reject → rewrite), failure recovery (timeouts, circuit breaker, template fallback, stale-job dropping), and an end-to-end outcome a single prompt can't produce reliably.

Also relevant: Grand Prize (explainable, personalised match intelligence) and Best Use of Microsoft Foundry.
