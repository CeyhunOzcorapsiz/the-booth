# Running The Booth for free

The Booth runs with **no accounts and no keys**: the crew falls back to deterministic templates. You only need a model provider to switch on the model-backed agents. Everything below has a free option. Check each offer's current terms before signing up; they change.

## 1. Models

Pick one and put it in `.env` (copy `.env.example`).

### Option A — Microsoft Foundry (recommended for the submission)

Free routes to Azure credit:

- **Azure for Students**: credit with no credit card, for verified students. https://azure.microsoft.com/free/students
- **Azure free account**: starter credit for the first 30 days (card required for identity). https://azure.microsoft.com/free

Then:

1. Open https://ai.azure.com and create a project (this creates a Foundry resource).
2. **Models + endpoints → Deploy model** → choose a small, cheap chat model such as `gpt-4.1-mini` (Global Standard). A full broadcast is a few hundred short calls, which costs cents.
3. Copy the endpoint and key from the deployment page.

```dotenv
BOOTH_LLM=foundry
FOUNDRY_ENDPOINT=https://<your-resource>.openai.azure.com/openai/v1/
FOUNDRY_API_KEY=<key>
FOUNDRY_MODEL=<deployment name, e.g. gpt-4.1-mini>
```

The endpoint must be the OpenAI **v1** endpoint (ending in `/openai/v1/`).

### Option B — GitHub Models (free, rate limited; good for development)

1. Create a fine-grained personal access token with the **Models: read** permission: https://github.com/settings/personal-access-tokens
2. Set:

```dotenv
BOOTH_LLM=github
GITHUB_TOKEN=<token>
GITHUB_MODEL=openai/gpt-4.1-mini
```

The free tier allows a limited number of requests per day, so keep `BOOTH_LLM_MIN_IMPORTANCE=0.6` or higher (only big moments use the model) and use one viewer at a time.

### Keeping usage low

| Variable | Default | Effect |
|---|---|---|
| `BOOTH_LLM_MIN_IMPORTANCE` | `0.5` | Only moments at least this important use the model; the rest use templates |
| `BOOTH_LLM_CONCURRENCY` | `2` | Parallel model calls |
| `BOOTH_LLM_TIMEOUT` | `12` | Seconds before a call falls back to a template |

Segments are cached per (event, viewer profile), so replaying the same seed with the same profile costs nothing after the first run.

## 2. Voice

- **Default:** the browser's built-in speech synthesis. Free, no key, works offline.
  A line is only read by a voice of its own language (a Turkish voice reading Japanese says the numbers in Turkish), so a language with no installed voice stays silent and the feed says why. Windows usually ships one or two languages; **Microsoft Edge** has free natural voices, female and male, for all 12 languages, so record demos in Edge. Viewers pick a female or male commentator in the setup dialog.
- **Pronunciation:** before speaking, each line is rewritten the way a commentator in that language says it (`frontend/speakable.js`): scores (`0-2` → "0 a 2", "0 対 2"), percentages ("yüzde 62", "62 Prozent"), units, decimal commas, `45+3'`, `99/100`, and abbreviations spelled with that language's letter names ("FC" → "F C", "fe ce", "エフシー").
- **Better:** Azure AI Speech neural voices (one female and one male voice per language) on the free F0 tier (a monthly allowance of neural text-to-speech, enough for demos). `infra/deploy.sh` creates it, or set `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION`. The server proxies requests so the key stays private, caches repeated lines and stops at `BOOTH_SPEECH_DAILY_CHARS` per day.

## 3. Hosting

**Azure Container Apps** has a monthly free grant of vCPU-seconds, memory and requests that covers a demo, and scales to zero when nobody is watching. The image is built by GitHub Actions and stored in GitHub Container Registry, which is free for public images (building in Azure would need a paid Azure Container Registry).

`bash infra/deploy.sh` does the whole setup; see [DEPLOY.md](DEPLOY.md). Keys are stored as Container Apps secrets, never in the image or the repository.

## 4. Development tools

- **GitHub Copilot**: Copilot Free for everyone; Copilot Pro is free for verified students through the GitHub Student Developer Pack (https://education.github.com/pack).
- **GitHub Container Registry**: free for public images; CI publishes `ghcr.io/ceyhunozcorapsiz/the-booth`.
- **GitHub Actions**: free for public repositories. CI runs tests and lint on every push.
