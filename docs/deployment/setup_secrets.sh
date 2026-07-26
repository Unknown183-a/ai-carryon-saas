#!/usr/bin/env bash
# Idempotent alternative to the manual `for VAR in ...; do gcloud secrets
# create ...` loop in this same folder's README.md ("Moving .env values
# into Secret Manager" section). Same list of vars, same one-secret-per-
# env-var-name convention — the difference is this script checks whether
# each secret already exists and adds a new version instead of failing on
# a re-run, so it's safe to use for the initial creation AND for later
# key rotations (see the README's "Rotating a key in production" section
# — this script IS step 1 of that process, just automated).
#
# Requires: gcloud CLI, already `gcloud auth login`'d, project selected
# (or pass it as $2).
#
# Usage:
#   cd docs/deployment
#   ./setup_secrets.sh ../../.env my-gcp-project-id

set -euo pipefail

ENV_FILE="${1:-.env}"
PROJECT_ID="${2:-$(gcloud config get-value project 2>/dev/null)}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "No project ID given and none set via 'gcloud config set project'. Usage: $0 <env-file> <project-id>" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi

# Same var list as the README's manual loop — FIREBASE_PROJECT_ID and
# RATE_LIMIT_REQUESTS_PER_MINUTE are deliberately excluded (non-secret
# config, meant to stay as plain --set-env-vars per the README).
SECRET_VARS=(
  FIREBASE_SERVICE_ACCOUNT_JSON
  UPSTASH_REDIS_REST_URL
  UPSTASH_REDIS_REST_TOKEN
  QDRANT_URL
  QDRANT_API_KEY
  CHANNEL_SECRETS_ENCRYPTION_KEY
  GEMINI_API_KEY
  GROQ_API_KEY
  OPENAI_API_KEY
  YOUTUBE_CLIENT_SECRETS_B64
  YOUTUBE_TOKEN_B64
  ELEVENLABS_API_KEY
  CELERY_BROKER_URL
  INTERNAL_SCHEDULER_TOKEN
)

echo "Project: $PROJECT_ID"
echo "Reading values from: $ENV_FILE"
echo

gcloud services enable secretmanager.googleapis.com --project "$PROJECT_ID" >/dev/null

created=0
updated=0
skipped=0

for VAR in "${SECRET_VARS[@]}"; do
  value="$(grep -E "^${VAR}=" "$ENV_FILE" | head -1 | cut -d'=' -f2-)"

  if [[ -z "$value" ]]; then
    echo "  skip     $VAR (empty or not set in $ENV_FILE)"
    skipped=$((skipped + 1))
    continue
  fi

  if gcloud secrets describe "$VAR" --project "$PROJECT_ID" >/dev/null 2>&1; then
    printf '%s' "$value" | gcloud secrets versions add "$VAR" \
      --project "$PROJECT_ID" --data-file=- >/dev/null
    echo "  updated  $VAR (new version — remember both Cloud Run services need a redeploy to pick it up, per the README)"
    updated=$((updated + 1))
  else
    printf '%s' "$value" | gcloud secrets create "$VAR" \
      --project "$PROJECT_ID" --data-file=- --replication-policy=automatic >/dev/null
    echo "  created  $VAR"
    created=$((created + 1))
  fi
done

echo
echo "Done. Created: $created, updated: $updated, skipped (empty): $skipped."
echo "deploy.yml's secrets: mapping already expects these exact names — nothing else to sync."
