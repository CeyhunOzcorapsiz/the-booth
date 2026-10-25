#!/usr/bin/env bash
# One-shot Azure setup for The Booth. Run after `az login`, from the repository root:
#
#   bash infra/deploy.sh                      # everything: Foundry model, speech, telemetry, Container App
#   bash infra/deploy.sh --local-only         # only the Foundry model (+ speech), written to .env for local runs
#
# Creates (all in one resource group, so `az group delete` removes everything):
#   - Microsoft Foundry (AI Services) resource + a gpt-4.1-mini deployment
#   - Azure AI Speech on the free F0 tier (neural voices; skipped if the subscription already has an F0)
#   - Log Analytics + Application Insights (agent traces)
#   - Azure Container Apps environment + app, pulling the public image built by GitHub Actions (GHCR)
# Secrets go into .env (git-ignored) and Container Apps secrets, never into the repository.
set -euo pipefail

RG="${RG:-the-booth-rg}"
LOCATION="${LOCATION:-swedencentral}"
AI_NAME="${AI_NAME:-booth-ai-$RANDOM}"
SPEECH_NAME="${SPEECH_NAME:-booth-speech-$RANDOM}"
MODEL="${MODEL:-gpt-4.1-mini}"
MODEL_VERSION="${MODEL_VERSION:-2025-04-14}"
CAPACITY="${CAPACITY:-50}"
APP="${APP:-the-booth}"
IMAGE="${IMAGE:-ghcr.io/ceyhunozcorapsiz/the-booth:latest}"
LOCAL_ONLY=false
[[ "${1:-}" == "--local-only" ]] && LOCAL_ONLY=true

step() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }

az account show --query "{subscription:name, user:user.name}" -o table

step "Resource group $RG ($LOCATION)"
az group create -n "$RG" -l "$LOCATION" -o none

step "Microsoft Foundry resource $AI_NAME"
az cognitiveservices account create -n "$AI_NAME" -g "$RG" -l "$LOCATION" \
  --kind AIServices --sku S0 --custom-domain "$AI_NAME" --yes -o none

step "Model deployment $MODEL ($MODEL_VERSION, GlobalStandard, capacity $CAPACITY)"
az cognitiveservices account deployment create -n "$AI_NAME" -g "$RG" \
  --deployment-name "$MODEL" --model-name "$MODEL" --model-version "$MODEL_VERSION" \
  --model-format OpenAI --sku-name GlobalStandard --sku-capacity "$CAPACITY" -o none

ENDPOINT="https://$AI_NAME.openai.azure.com/openai/v1/"
KEY="$(az cognitiveservices account keys list -n "$AI_NAME" -g "$RG" --query key1 -o tsv)"

step "Azure AI Speech (free F0 tier)"
SPEECH_KEY=""
if az cognitiveservices account create -n "$SPEECH_NAME" -g "$RG" -l "$LOCATION" \
     --kind SpeechServices --sku F0 --yes -o none 2>/dev/null; then
  SPEECH_KEY="$(az cognitiveservices account keys list -n "$SPEECH_NAME" -g "$RG" --query key1 -o tsv)"
else
  echo "Speech F0 not created (only one F0 per subscription is allowed). The browser voice will be used."
fi

step "Writing .env (git-ignored)"
[[ -f .env ]] && cp .env .env.backup
cat > .env <<ENV
BOOTH_LLM=foundry
FOUNDRY_ENDPOINT=$ENDPOINT
FOUNDRY_API_KEY=$KEY
FOUNDRY_MODEL=$MODEL
BOOTH_LLM_MIN_IMPORTANCE=0.5
AZURE_SPEECH_KEY=$SPEECH_KEY
AZURE_SPEECH_REGION=$LOCATION
ENV
echo "Foundry endpoint: $ENDPOINT (keys stored in .env)"

if $LOCAL_ONLY; then
  step "Done. Start the app locally and the crew will use $MODEL."
  exit 0
fi

step "Application Insights"
az extension add --name application-insights --upgrade -o none 2>/dev/null || true
az monitor app-insights component create --app "$APP-insights" -g "$RG" -l "$LOCATION" \
  --kind web --application-type web -o none
INSIGHTS="$(az monitor app-insights component show --app "$APP-insights" -g "$RG" --query connectionString -o tsv)"

step "Container App $APP from $IMAGE"
az extension add --name containerapp --upgrade -o none 2>/dev/null || true
az containerapp up -n "$APP" -g "$RG" -l "$LOCATION" --image "$IMAGE" \
  --ingress external --target-port 8000 -o none
az containerapp secret set -n "$APP" -g "$RG" \
  --secrets foundry-key="$KEY" insights="$INSIGHTS" speech-key="${SPEECH_KEY:-none}" -o none
SPEECH_ENV=()
if [[ -n "$SPEECH_KEY" ]]; then
  SPEECH_ENV=(AZURE_SPEECH_KEY=secretref:speech-key AZURE_SPEECH_REGION="$LOCATION")
fi
# One replica: rate limits and the model budget are kept in memory per replica.
az containerapp update -n "$APP" -g "$RG" --min-replicas 0 --max-replicas 1 \
  --set-env-vars BOOTH_LLM=foundry FOUNDRY_ENDPOINT="$ENDPOINT" FOUNDRY_MODEL="$MODEL" \
  FOUNDRY_API_KEY=secretref:foundry-key APPLICATIONINSIGHTS_CONNECTION_STRING=secretref:insights \
  BOOTH_TRUST_PROXY=true BOOTH_LLM_DAILY_BUDGET=1500 "${SPEECH_ENV[@]}" -o none

URL="https://$(az containerapp show -n "$APP" -g "$RG" --query properties.configuration.ingress.fqdn -o tsv)"
step "Live at $URL"
echo "Health: $URL/api/health"
echo "Remove everything later with: az group delete -n $RG --yes"
