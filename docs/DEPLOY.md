# Deploying to Azure

Everything is scripted in [`infra/deploy.sh`](../infra/deploy.sh). It creates one resource group, so deleting that group removes everything.

| Resource | Why | Cost |
|---|---|---|
| Microsoft Foundry (AI Services) + `gpt-4.1-mini` deployment | Model behind the agents | Pay per token; a full broadcast is a few cents of credit |
| Azure AI Speech (F0) | Neural voices for the audio-first mode | Free tier |
| Application Insights + Log Analytics | Traces of every agent run, model call, tool call and crew hand-off | Free monthly ingestion allowance |
| Azure Container Apps | Hosts the app, scales to zero | Free monthly grant |
| GitHub Container Registry | Hosts the image built by CI | Free for public images |

## Steps

1. Get an Azure subscription with credit (Azure for Students or an Azure free account, see [FREE_SETUP.md](FREE_SETUP.md)).
2. Install the Azure CLI and sign in. You do the sign-in yourself in the browser:

   ```bash
   winget install --exact --id Microsoft.AzureCLI
   az login
   ```

3. **Model only** (for local development and the demo recording):

   ```bash
   bash infra/deploy.sh --local-only
   ```

   This writes `.env` with the Foundry endpoint, key and model. Restart the app; the badge in the top bar switches from `OFFLINE · TEMPLATES` to `FOUNDRY · gpt-4.1-mini`.

4. **Full deployment** (public URL for judges):

   The Container App pulls `ghcr.io/ceyhunozcorapsiz/the-booth:latest`, which CI publishes on every push to `main`. The image must be **public** first: GitHub → your profile → Packages → `the-booth` → Package settings → Change visibility → Public.

   ```bash
   bash infra/deploy.sh
   ```

   The script prints the public URL. Check `<url>/api/health`: `llm.configured` should be `true`.

## Options

Override any of these as environment variables:

| Variable | Default |
|---|---|
| `RG` | `the-booth-rg` |
| `LOCATION` | `swedencentral` |
| `MODEL` / `MODEL_VERSION` | `gpt-4.1-mini` / `2025-04-14` |
| `CAPACITY` | `50` (thousand tokens per minute) |
| `APP` | `the-booth` |
| `IMAGE` | `ghcr.io/ceyhunozcorapsiz/the-booth:latest` |

If the model deployment fails with a quota error (common on student subscriptions), try another `LOCATION` (for example `eastus2`), a lower `CAPACITY`, or `MODEL=gpt-4o-mini MODEL_VERSION=2024-07-18`.

## Protection on the public URL

The deployment runs one replica with `BOOTH_TRUST_PROXY=true` (client addresses come from the Container Apps ingress) and `BOOTH_LLM_DAILY_BUDGET=1500` agent runs per day. When the budget is spent the crew keeps broadcasting on templates. See the README section "Running it in public" for all limits.

## Observing the crew

In Application Insights → **Transaction search** (or the Agent Framework / GenAI views), each director job is a `booth.job` span with the hand-offs (`stats-producer.done`, `fact-checker.rejected`, `localizer.done`, …) as span events, and Agent Framework adds child spans for every agent run, model call and tool call.

## Tear down

```bash
az group delete -n the-booth-rg --yes
```
