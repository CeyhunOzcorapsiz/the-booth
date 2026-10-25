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

- **Now:** the browser's built-in speech synthesis. Free, no key, works offline.
- **Planned:** Azure AI Speech has a free tier (F0) with a monthly allowance of neural text-to-speech, enough for demos.

## 3. Hosting

**Azure Container Apps** has a monthly free grant of vCPU-seconds, memory and requests that covers a demo. With the Azure CLI:

```bash
az containerapp up --name the-booth --resource-group the-booth-rg --location westeurope \
  --source . --ingress external --target-port 8000 \
  --env-vars BOOTH_LLM=foundry FOUNDRY_ENDPOINT=... FOUNDRY_MODEL=... FOUNDRY_API_KEY=secretref:foundry-key
```

Store the key as a Container Apps secret, never in the image or the repository.

## 4. Development tools

- **GitHub Copilot**: Copilot Free for everyone; Copilot Pro is free for verified students through the GitHub Student Developer Pack (https://education.github.com/pack).
- **GitHub Actions**: free for public repositories. CI runs tests and lint on every push.
