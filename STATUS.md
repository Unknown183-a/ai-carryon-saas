# Current Status

*(Update this every time you stop working. Single source of truth for "where are we.")*

| Field | Value |
|---|---|
| **Active phase** | Phase 9 — Deployment (mainline); Phase 11 — Frontend Dashboard also built, out of order on purpose |
| **Last updated by** | Claude |
| **Last updated on** | 2026-07-26 |
| **Blocking issue, if any** | Phase 7 (this repo's newest mainline work) hasn't been exercised against real ElevenLabs/YouTube/ffmpeg — everything in `tests/phase7_async_workers_test.py` runs against faked TTS/upload calls and a faked `subprocess.run`, same convention as Phase 4/5's original fake-first test scripts before their real-keys smoke tests existed. `render_worker.py` does shell out to a REAL `ffmpeg` binary in production (not faked at the binary level, only in the test script) — a real local run needs `ffmpeg` installed (`brew install ffmpeg` on the Mac, already in `docker/Dockerfile` for the container). Phase 6's own blocking issue (real Firebase/Firestore end-to-end pass) is still open too — nothing in Phase 7 required it, but it's still worth doing before either phase is trusted beyond local dev. So: before trusting Phase 7 beyond local dev, run a real end-to-end pass with real `ELEVENLABS_API_KEY`, real `YOUTUBE_CLIENT_SECRETS_B64`/`YOUTUBE_TOKEN_B64`, real `CELERY_BROKER_URL` (Upstash's Redis-protocol connection string, not the REST one — see `app/workers/celery_app.py`'s module docstring), and a real `ffmpeg` binary — the same way Phases 3-5 already got theirs (a `phase7_real_keys_smoke_test.py`, not yet written, is the natural next step whenever real keys are available). Separately, **Phase 11's `npm run build` has not been run to completion anywhere yet** — only `npx tsc --noEmit` (clean, zero errors) was verified, in an environment that couldn't reach `fonts.googleapis.com` for `next/font/google`. Run a real `npm run build` before trusting it beyond local dev. |
| **Next concrete action** | Mainline: begin Phase 8 — see `phases/phase-08-scheduler/PHASE.md`. Worth a real-keys smoke test of Phase 7 first (see row above). Frontend: run `npm install && npm run build` for real in `frontend/` to confirm the build that couldn't be verified in the authoring sandbox; also add the missing `GET/PATCH /channels/{id}/provider-keys` backend route the Providers screen is currently honest about not having. Deployment side-track: create the GCP service account + repo secrets (`GCP_SA_KEY`, `GCP_PROJECT_ID`) per `docs/deployment/README.md`, then merge to `main` to trigger the first real deploy of both Cloud Run services. |
| **Latest work report** | `work-reports/daily/2026-07-25-phase8-scheduler-done.md` (mainline); `work-reports/daily/2026-07-25-phase11-frontend-dashboard-done.md` (frontend, out of order); `work-reports/daily/2026-07-26-phase9-deployment.md` (deployment side-track) |

## Independent side-track: Phase 9 (CI/CD)

Built out of order on purpose — Phase 9 is the one phase the guide explicitly allows starting early ("or earlier ... recommended, don't wait"). Doesn't block or get blocked by Phase 4/5.

- [x] `docker/Dockerfile` — updated in Phase 7 to add `ffmpeg` + `fonts-dejavu-core` system packages
- [x] `.github/workflows/deploy.yml` — test + build + push to `ghcr.io` verified green end-to-end
- [x] Deploy target decision: **Cloud Run**, for both pieces — matches the SAD (Ch.17); reasoning in `docs/deployment/README.md`
- [x] Worker's continuous-run requirement (flagged here previously) resolved: `ai-carryon-worker` is a second Cloud Run service, pinned `--min-instances=1 --no-cpu-throttling`, with a new `backend/app/workers/worker_entrypoint.py` wrapper so Cloud Run's health polling has something to check (a bare Celery process doesn't listen on any port). Trade-off: that instance is billed continuously, 24/7 — see the cost note in the runbook; a small always-on VM was the other option considered and could still be revisited later.
- [x] `docker-compose.yml` — local API + worker testing (unaffected by the Cloud Run-specific worker wrapper; local dev still runs plain `celery -A app.workers.celery_app worker`)
- [x] `docs/deployment/README.md` — GCP service account setup, Secret Manager migration, key rotation, reachability checks, rollback for both services
- [ ] GCP service account + repo secrets (`GCP_SA_KEY`, `GCP_PROJECT_ID`) not created yet — one-time manual step, see runbook. Until then, `deploy.yml`'s `deploy` job will fail at the `auth` step (expected; `test`/`build` still pass).

## Independent side-track: Phase 11 (Frontend Dashboard)

Built out of order on purpose — PHASE.md explicitly allows this ("Depends on: Phase 6 at minimum ... ideally Phase 10 too"). Workspace only has Phase 6 (multi-tenancy) done on the mainline, so that minimum is satisfied; Phase 10 isn't done yet, so the live-status panel only has plain `/health` to poll rather than richer Health Agent data.

- [x] Next.js 14 / TypeScript / Tailwind app in `frontend/`
- [x] Login/Signup against Firebase Auth, auto-creates a Workspace on sign-in (Ch.12c)
- [x] Full nav: Dashboard, Channels, Analytics, Billing, API Providers, Team, Settings, Logs
- [x] Create-Channel form — every field matches `backend/app/models/channel.py` exactly
- [x] Live status view — polls `/health` (no WebSocket route exists on the backend yet)
- [x] Provider connection screens, honestly flagging a real backend gap (see below)
- [ ] `npm run build` run to completion — only `npx tsc --noEmit` (clean) was verified so far
- [ ] Backend: `GET/PATCH /channels/{id}/provider-keys` route — doesn't exist yet, so the Providers screen can't show connection status or let a key be rotated without recreating the channel

See `phases/phase-11-frontend-dashboard/PHASE.md`'s Handoff Notes for the full detail.

## Prerequisites checklist

Copied from `BUILD_GUIDE.md` §2 — do these once, up front, regardless of which phase you're on:

- [x] GitHub repo created (private is fine to start)
- [x] Firebase project created — console.firebase.google.com (Spark/free plan)
- [x] Upstash account for Redis — upstash.com (free tier, REST-based) *(Phase 7: also its Redis-protocol `rediss://` connection string, same instance, used as Celery's broker/backend)*
- [x] Qdrant Cloud account — cloud.qdrant.io (free 1GB cluster) *(real cluster created and verified — see Phase 5's real-keys work report)*
- [x] Gemini API key — aistudio.google.com
- [ ] Google Cloud project for Cloud Run — no longer optional as of this Phase 9 work; needed now for both the API and worker services, plus Secret Manager. See `docs/deployment/README.md`'s one-time setup section.
- [ ] ElevenLabs API key for voice — *(no longer optional as of Phase 7 — `voice_worker.py` needs `ELEVENLABS_API_KEY` for real runs; the code runs fine without it in tests via the fake, per the Blocking Issue row above)*
- [ ] YouTube Data API OAuth credentials — console.cloud.google.com *(needed for `upload_worker.py`'s real runs — `YOUTUBE_CLIENT_SECRETS_B64` / `YOUTUBE_TOKEN_B64`, base64-encoded per the old pipeline's pattern, see `integrations/youtube/client.py`)*
- [x] Python 3.11+
- [x] Groq API key — console.groq.com *(this checklist predates Phase 4; add it to BUILD_GUIDE.md §2 next time it's edited)*
- [x] Serper.dev API key — serper.dev *(same note — used for the Research Agent's web search, not originally listed here either)*
- [ ] Node 20+
- [x] Docker Desktop
- [ ] `ffmpeg` installed locally *(new as of Phase 7 — `render_worker.py` shells out to the real binary; `brew install ffmpeg` on the Mac. Already added to `docker/Dockerfile` for the containerized path.)*

## Phase index

| Phase | Folder | Depends on |
|---|---|---|
| 0 — Repo & Skeleton | `phases/phase-00-repo-skeleton/` | — |
| 1 — Firebase Auth + Firestore | `phases/phase-01-firebase-auth-firestore/` | 0 |
| 2 — FastAPI Gateway (shell) | `phases/phase-02-fastapi-gateway/` | 1 |
| 3 — Redis (Upstash) | `phases/phase-03-redis-upstash/` | 2 |
| 4 — LangGraph, single hardcoded channel | `phases/phase-04-langgraph-core-agents/` | 3 |
| 5 — Qdrant + RAG | `phases/phase-05-qdrant-rag/` | 4 |
| 6 — Multi-Tenancy: Channel Brain / Factory | `phases/phase-06-multi-tenancy-channel-factory/` | 5, 3 |
| 7 — Async Workers | `phases/phase-07-async-workers/` | 6 |
| 8 — Scheduler | `phases/phase-08-scheduler/` | 7 |
| 9 — Deployment | `phases/phase-09-deployment/` | 8 (or earlier) — **built early, side-track above** |
| 10 — Monitoring & Alerts | `phases/phase-10-monitoring-alerts/` | 9 |
| 11 — Frontend Dashboard | `phases/phase-11-frontend-dashboard/` | 6 min, ideally 10 — **built early, see side-track above** |
| 12 — Learning Agent | `phases/phase-12-learning-agent/` | 11 + real analytics data |
