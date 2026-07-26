# Deployment Runbook

Deploy target: **Cloud Run** (per the SAD, Ch.17 — GitHub → Actions → Docker →
Cloud Run → load balancer → FastAPI). Railway is documented in `deploy.yml` as
a fallback but is not the chosen path.

Two Cloud Run services are deployed from the same image:
- **`ai-carryon-gateway`** — the FastAPI API. Request-driven, scales to zero
  when idle, same as any normal Cloud Run service.
- **`ai-carryon-worker`** — the Celery worker. Cloud Run isn't built for a
  continuously-running consumer by default, so this service is pinned with
  `--min-instances=1 --max-instances=1 --no-cpu-throttling` (always one
  instance running, billed continuously) and its container entrypoint is
  overridden to `python -m app.workers.worker_entrypoint` instead of the
  plain `celery` command. That wrapper starts the real Celery worker as a
  child process and also runs a minimal HTTP server on `$PORT` that always
  replies 200 — purely so Cloud Run's health polling considers the instance
  up, since a bare Celery process never listens on any port. See that file's
  docstring (`backend/app/workers/worker_entrypoint.py`) for the full reasoning.
  It is NOT used for local dev — `docker-compose.yml` runs the plain `celery`
  command there, since Cloud Run's health-polling requirement doesn't apply
  locally.

## One-time GCP setup

1. Create (or reuse) a GCP project. Note the project ID — it's `GCP_PROJECT_ID`.
2. Enable APIs: Cloud Run, Artifact Registry (or keep using `ghcr.io`, which
   Cloud Run can pull from directly), Secret Manager.
3. Create a deploy service account:
   ```
   gcloud iam service-accounts create ai-carryon-deployer \
     --display-name="AI CarryON CI deployer"
   ```
4. Grant it the roles it needs:
   ```
   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:ai-carryon-deployer@$PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/run.admin"

   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:ai-carryon-deployer@$PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/iam.serviceAccountUser"

   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:ai-carryon-deployer@$PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor"
   ```
5. Create and download its key:
   ```
   gcloud iam service-accounts keys create key.json \
     --iam-account=ai-carryon-deployer@$PROJECT_ID.iam.gserviceaccount.com
   ```
6. In the GitHub repo → Settings → Secrets and variables → Actions, add:
   - `GCP_PROJECT_ID` — the project ID from step 1
   - `GCP_SA_KEY` — the full contents of `key.json`
   Delete `key.json` locally once it's pasted in — don't commit it.

## Moving `.env` values into Secret Manager

Every variable in `.env.example` that isn't build-time config becomes a
Secret Manager secret, then gets wired into both Cloud Run services via
`--set-secrets` (already in `deploy.yml`'s `secrets:` blocks — the API and
the worker get the same set, since the worker needs LLM/voice/YouTube keys
just as much as the API needs Firebase/Redis/Qdrant). To create them:

```
for VAR in FIREBASE_SERVICE_ACCOUNT_JSON UPSTASH_REDIS_REST_URL \
  UPSTASH_REDIS_REST_TOKEN QDRANT_URL QDRANT_API_KEY \
  CHANNEL_SECRETS_ENCRYPTION_KEY GEMINI_API_KEY GROQ_API_KEY \
  OPENAI_API_KEY YOUTUBE_CLIENT_SECRETS_B64 YOUTUBE_TOKEN_B64 \
  ELEVENLABS_API_KEY CELERY_BROKER_URL INTERNAL_SCHEDULER_TOKEN; do
    printf '%s' "${!VAR}" | gcloud secrets create "$VAR" --data-file=-
done
```

(Run this from a shell that has your real local `.env` sourced — never
paste real secret values into a commit, an issue, or this file.)

`FIREBASE_PROJECT_ID` and `RATE_LIMIT_REQUESTS_PER_MINUTE` are non-secret
config and can stay as plain `--set-env-vars` if the app needs them at
runtime — add them to the relevant `deploy.yml` flags line if so, rather
than Secret Manager.

### Rotating a key in production

1. Create a new version of the secret: `gcloud secrets versions add VAR_NAME --data-file=-`
2. Redeploy (push to `main`, or `gcloud run services update <service> --region <region>`
   with no image change — Cloud Run picks up `:latest` secret versions on
   new revisions only, so a redeploy is required, not just the secret update).
   Do this for BOTH `ai-carryon-gateway` and `ai-carryon-worker` if the
   rotated key is one the worker also uses (most of them are).
3. Confirm API `/health` still returns 200, and check the worker service's
   logs show it reconnected cleanly, before considering the rotation done.
4. Disable (don't delete) the old secret version once you've confirmed the
   new one works, in case of rollback.

## Confirming Redis/Qdrant reachability from Cloud Run

Both Upstash Redis and Qdrant Cloud are public REST/TLS endpoints reachable
over the internet — Cloud Run's default egress (no VPC connector) can reach
them with no extra networking config, for both the API and worker services.
After the first deploy, confirm the API side with:

```
curl https://<cloud-run-url>/health
```

and check the health response includes passing Redis and Qdrant checks (the
Health Agent from Ch.18 covers this ongoing, once Phase 10 is built — for
now, `/health` returning 200 is the Phase 9 bar). For the worker, there's no
equivalent single endpoint to check business-logic health (the `/health`-like
port on `ai-carryon-worker` only proves the container is alive, per the
`worker_entrypoint.py` docstring) — confirm it's actually consuming tasks by
checking Cloud Run's logs for the service, or by queuing a real task and
watching it get picked up.

## Rollback

Cloud Run keeps prior revisions automatically for both services. To roll
back the API without a new deploy:

```
gcloud run services update-traffic ai-carryon-gateway \
  --region asia-south1 \
  --to-revisions=<previous-revision-name>=100
```

Same command with `ai-carryon-worker` in place of `ai-carryon-gateway` rolls
back the worker. List revisions with
`gcloud run revisions list --service <service-name> --region asia-south1`.

## Cost note: two always-considered services

`ai-carryon-gateway` scales to zero when idle, like any normal Cloud Run
service — you only pay for actual requests. `ai-carryon-worker` is pinned at
`--min-instances=1`, so it's billed continuously, 24/7, regardless of task
volume. This is the trade-off that came with choosing "Cloud Run for the
worker, made always-on" over a separate small always-on VM — worth
revisiting if the always-on Cloud Run instance's cost turns out to be worse
than just running a cheap VM (e.g. Compute Engine e2-micro) for the worker
instead. Not switched to that here since the decision was made to stay on
Cloud Run for both pieces.

## Cloud Run vs Railway — why Cloud Run

Railway was the short-term option while no GCP project existed yet. Now that
GCP is set up (Firebase already lives there from Phase 1), Cloud Run keeps
everything in one ecosystem and is what the architecture doc specifies. The
Railway block stays in `deploy.yml`, commented, in case that ever changes.

## Automating the two manual steps above

`setup_secrets.sh` (this folder) automates the "Moving `.env` values into
Secret Manager" for-loop above — same var list, but idempotent (creates on
first run, adds a new version on any re-run, so it also covers "Rotating a
key in production" step 1):

```
cd docs/deployment
./setup_secrets.sh ../../.env $PROJECT_ID
```

`tests/phase9_deployed_reachability_test.py` (repo root) automates the
"Confirming Redis/Qdrant reachability" section above, and also covers the
worker-side gap this doc calls out ("no equivalent single endpoint to check
business-logic health" for `ai-carryon-worker`) — since it checks Redis/Qdrant
directly with real credentials rather than through any HTTP endpoint:

```
python tests/phase9_deployed_reachability_test.py
# optionally also curl the gateway's /health in the same run:
DEPLOYED_BASE_URL=https://<cloud-run-gateway-url> python tests/phase9_deployed_reachability_test.py
```
