<!-- Self-contained phase brief. Companion docs: ../../BUILD_GUIDE.md (full build order) and ../../docs/architecture/AI-CarryON-Architecture.html (the why). -->

## Phase 9 — Deployment
*(SAD reference: Chapter 17 — Deployment)*

**Goal:** GitHub → GitHub Actions → Docker → hosted, on every merge to `main`.

**Depends on:** Phase 8 (or can start earlier if you want CI running from Phase 2 onward — recommended, don't wait).

**Tasks:**
- [x] `docker/Dockerfile` for the FastAPI backend
- [x] `.github/workflows/deploy.yml` — build, test, push, deploy on merge to `main`
- [ ] Deploy target: Cloud Run (matches the SAD) or keep Railway short-term if deferring GCP migration — document the choice here once made
- [ ] Move all secrets from local `.env` into the deploy target's secret manager
- [ ] Confirm Redis (Upstash) and Qdrant (Cloud) are reachable from the deployed environment, not just localhost

**Definition of Done:** a merge to `main` results in a live, publicly reachable `/health` endpoint returning `200`, with zero manual deploy steps.

**Handoff Notes:**
> Dockerfile builds `backend/` with `backend/requirements.txt`, runs `uvicorn app.api.main:app`, honors `$PORT` for Cloud Run compatibility. CI (`deploy.yml`) runs on every push/PR: `test` job now runs `tests/phase3_redis_ratelimit_test.py` directly as a script (it self-mocks Upstash, fully CI-safe) — the file isn't pytest-shaped, so pytest was collecting it as a module and crashing; switched off pytest entirely. `tests/phase1_firebase_test.py` needs a real Firebase project + service account and creates/deletes a live user, so it's explicitly skipped in CI with a note to run it manually/locally. On `main`, `build` builds and pushes the image to `ghcr.io/<repo, lowercased>` — ghcr.io rejects uppercase in the repo owner (`Unknown183-a` broke the first attempt), fixed by lowercasing `github.repository` into an env var before tagging. Verified end-to-end green: `test` ✅, `build` ✅ (image visible under the repo's Packages tab), `deploy` is a documented no-op stub with commented Cloud Run and Railway blocks. Next: pick Cloud Run vs Railway, add matching secrets (`GCP_SA_KEY`/`GCP_PROJECT_ID` or `RAILWAY_TOKEN`), uncomment that block. Phase 4 work continues separately/independently.

---
