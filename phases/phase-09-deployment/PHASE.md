<!-- Self-contained phase brief. Companion docs: ../../BUILD_GUIDE.md (full build order) and ../../docs/architecture/AI-CarryON-Architecture.html (the why). -->

## Phase 9 — Deployment
*(SAD reference: Chapter 17 — Deployment)*

**Goal:** GitHub → GitHub Actions → Docker → hosted, on every merge to `main`.

**Depends on:** Phase 8 (or can start earlier if you want CI running from Phase 2 onward — recommended, don't wait).

**Tasks:**
- [x] `docker/Dockerfile` for the FastAPI backend
- [x] `.github/workflows/deploy.yml` — build, test, push, deploy on merge to `main`
- [x] Deploy target: **Cloud Run** (matches the SAD) — documented in `docs/deployment/README.md`
- [x] `docker-compose.yml` for local API + worker testing
- [ ] Move all secrets from local `.env` into Cloud Run's Secret Manager — steps documented in `docs/deployment/README.md`; requires running the `gcloud secrets create` loop against real values, not something to do from a shared doc
- [ ] Create the GCP service account + repo secrets (`GCP_SA_KEY`, `GCP_PROJECT_ID`) — one-time manual step, see runbook
- [ ] First real deploy to confirm Redis (Upstash) and Qdrant (Cloud) are reachable from the deployed environment, not just localhost — `/health` should return 200 with both checks passing

**Definition of Done:** a merge to `main` results in a live, publicly reachable `/health` endpoint returning `200`, with zero manual deploy steps.

**Handoff Notes:**
> Dockerfile builds `backend/` with `backend/requirements.txt`, runs `uvicorn app.api.main:app`, honors `$PORT` for Cloud Run compatibility. CI (`deploy.yml`) runs on every push/PR: `test` job runs `tests/phase3_redis_ratelimit_test.py` directly as a script (self-mocked, CI-safe); `tests/phase1_firebase_test.py` needs real Firebase credentials so it's explicitly skipped in CI. `build` pushes to `ghcr.io/<repo, lowercased>`.
>
> This session: picked Cloud Run as the deploy target (SAD says so explicitly, and Firebase is already on GCP, so it keeps the stack in one ecosystem). Uncommented and finished the `deploy` job in `deploy.yml` — it now authenticates via `google-github-actions/auth`, deploys via `google-github-actions/deploy-cloudrun`, wires every secret in `.env.example` in through Cloud Run's `--set-secrets` (not plain env vars), and verifies `/health` after deploy. Added `docker-compose.yml` for local API+worker runs against real (not mocked) Upstash/Qdrant, since those are cloud services in every environment including local dev. Wrote `docs/deployment/README.md`: full GCP service-account setup, the Secret Manager migration commands, key rotation steps, reachability check, and rollback via `gcloud run services update-traffic`.
>
> Still open, and can't be finished from a shared/CI context: someone with GCP account access needs to actually run the service-account creation + `gcloud secrets create` commands from the runbook and add `GCP_SA_KEY`/`GCP_PROJECT_ID` as repo secrets. Once that's done, the very next merge to `main` should complete Phase 9's Definition of Done automatically — no code changes needed, just the one-time account setup.

---
