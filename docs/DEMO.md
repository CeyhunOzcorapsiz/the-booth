# Demo video (under 2 minutes)

Rules from the brief: **under 2:00**, show the project running, public link (YouTube / Vimeo), **no third-party trademarks or copyrighted music**. Our clubs, players and logo are fictional and generated, and we don't use the Premier League name or crest on screen. Record in English.

## Before recording

- Foundry configured (`bash infra/deploy.sh --local-only`): the top-bar badge reads `FOUNDRY · gpt-4.1-mini`, and segments say `AI · gpt-4.1-mini`.
- Seed **119**: Ember Athletic lead 2–0 after an hour; Northstar FC come back to win 3–2 with goals at 78', 82' and 90'.
- Run each broadcast once before recording so segments are cached and appear instantly.
- Deep links skip the setup dialog: `/?live=1&seed=119&lang=tr&style=beginner&accessible=1&start=76&speed=10` and `/?view=compare&seed=119`.
- Browser at 1440×900, zoom 100%, notifications off. Record with OBS Studio (free) or the Xbox Game Bar (Win+G).
- Voice: use your own narration, or the app's own voice output. No background music, or only royalty-free music you have the rights to.

## Script

| Time | On screen | Narration |
|---|---|---|
| 0:00–0:12 | Black slide: "One match. One crew. One broadcast. For everyone?" | "Every live match is made by a crew, but that crew makes one show, in one language, for everyone." |
| 0:12–0:25 | The Booth, setup dialog: pick Turkish, New to football, Audio-first | "The Booth gives every fan their own crew. I pick my language, my style, and audio-first mode for blind and low-vision fans." |
| 0:25–0:45 | Go live at minute 76. Pitch moves, feed fills, voice reads aloud, a rule explainer appears | "Agents commentate live. The guide explains the rules when they come up, and tells me where the ball is, because I can't see it." |
| 0:45–1:05 | Control room: director planned, stats producer tool calls, fact-checker approved / rejected, localizer | "Behind it is a multi-agent crew on Microsoft Agent Framework and Foundry. The director decides what matters to me. The stats producer pulls numbers with tool calls. The fact-checker blocks anything it can't trace to the data and sends it back for a rewrite." |
| 1:05–1:30 | "Same moment, 3 shows": the 90' winner, three columns | "Same goal, three fans: a hype call in English, a calm Turkish explainer, a tactical breakdown. Every line is verified. Click any line to see its sources." |
| 1:30–1:45 | Ask the booth: "Who's had more of the ball?" → answer with sources | "Fans can ask questions, answered only from the stats desk at the minute they're watching." |
| 1:45–1:58 | Application Insights trace, or the GitHub repo, then the end card | "It runs on Azure Container Apps with every agent hand-off traced in Application Insights. The Booth: one match, a broadcast for every fan." |

## Fallback if the model is unavailable on recording day

The app runs fully on templates. Record anyway and say "running on our deterministic fallback crew". Don't present template output as AI: the badge and the `template` tags on each segment show the source.
