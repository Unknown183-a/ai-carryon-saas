# Deployment Runbook

Deploy target: **Cloud Run** (per the SAD, Ch.17 — GitHub → Actions → Docker →
Cloud Run → load balancer → FastAPI). Railway is documented in `deploy.yml` as
a fallback but is not the chosen path.

## One-time GCP setup

1. Create (or reuse) a GCP project. Note the project ID — it's `GCP_PROJECT_ID`.
2. Enable APIs: Cloud Run, Artifact Registry (or keep using `ghcr.io`, which
   Cloud Run can pull from directly), Secret Manager.
3. Create a deploy service account:
   ```
   gcloud iam service-accounts create ai-carryon-deployer \
     --display-name="AI CarryON CI deployer"
   ```
4. Grant it the two roles it needs:
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
Secret Manager secret, then gets wired into the Cloud Run revision via
`--set-secrets` (already in `deploy.yml`'s `secrets:` block). To create them:

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
runtime — add them to the `deploy.yml` flags line if so, rather than
Secret Manager.

### Rotating a key in production

1. Create a new version of the secret: `gcloud secrets versions add VAR_NAME --data-file=-`
2. Redeploy (push to `main`, or `gcloud run services update <service> --region <region>`
   with no image change — Cloud Run picks up `:latest` secret versions on
   new revisions only, so a redeploy is required, not just the secret update).
3. Confirm `/health` still returns 200 before considering the rotation done.
4. Disable (don't delete) the old secret version once you've confirmed the
   new one works, in case of rollback.

## Confirming Redis/Qdrant reachability from Cloud Run

Both Upstash Redis and Qdrant Cloud are public REST/TLS endpoints reachable
over the internet — Cloud Run's default egress (no VPC connector) can reach
them with no extra networking config. After the first deploy, confirm with:

```
curl https://<cloud-run-url>/health
```

and check the health response includes passing Redis and Qdrant checks (the
Health Agent from Ch.18 covers this ongoing, once Phase 10 is built — for now,
`/health` returning 200 is the Phase 9 bar).

## Rollback

Cloud Run keeps prior revisions automatically. To roll back without a new
deploy:

```
gcloud run services update-traffic ai-carryon-gateway \
  --region asia-south1 \
  --to-revisions=<previous-revision-name>=100
```

List revisions with `gcloud run revisions list --service ai-carryon-gateway --region asia-south1`.

## Cloud Run vs Railway — why Cloud Run

Railway was the short-term option while no GCP project existed yet. Now that
GCP is set up (Firebase already lives there from Phase 1), Cloud Run keeps
everything in one ecosystem, scales to zero for this system's bursty/
scheduled workload (per Ch.17), and is what the architecture doc specifies.
The Railway block stays in `deploy.yml`, commented, in case that ever changes.
