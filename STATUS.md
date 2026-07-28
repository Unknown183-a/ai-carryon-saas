# Current Status

*(Update this every time you stop working. Single source of truth for "where are we.")*

| Field | Value |
|---|---|
| **Active phase** | Phase 10 — Monitoring & Alerts is code-complete (health_agent.py, alert_agent.py, email/dashboard notifications, Firestore incidents — see below). Phase 9 (deployment) and Phase 11 (frontend) also built, both still with one operational gap each — see Blocking issue. |
| **Last updated by** | Claude (Phase 9-11); Amit (auth verification add-on) |
| **Last updated on** | 2026-07-28 |
| **Blocking issue, if any** | **Phase 10** is code-complete and verified against real code paths (a real compiled LangGraph run, a real FastAPI `TestClient` request through the real `require_system_token` gate, a real simulated-Redis-outage-to-email run — see `tests/phase10_monitoring_test.py`, 24/24 passing) but **operationally unverified**: no real Redis/Qdrant/Firestore/YouTube/Resend credentials in this session, and no Cloud Scheduler job exists yet to actually call `/internal/health-check/run` on a timer (needs Phase 9's live Cloud Run URL to point at first). **Phase 9** itself is still one step from done: the GCP service account + repo secrets (`GCP_SA_KEY`, `GCP_PROJECT_ID`) haven't been created yet, so `deploy.yml`'s `deploy` job fails at the `auth` step (expected — `test`/`build` still pass). Carried over: Phase 7 still needs its real-keys smoke test, Phase 6's real Firebase/Firestore end-to-end pass is still open, and Phase 11's `npm run build` has never been run to completion. |
| **Next concrete action** | Create the GCP service account + repo secrets per `docs/deployment/README.md`, merge to `main` to trigger the first real deploy of both Cloud Run services — that closes Phase 9. Then add one more Cloud Scheduler job (5 min interval) → `/internal/health-check/run` with the `INTERNAL_SCHEDULER_TOKEN` header — that closes Phase 10. Frontend: run `npm install && npm run build` for real; add the missing `GET/PATCH /channels/{id}/provider-keys` backend route. |
| **Latest work report** | `work-reports/daily/2026-07-26-phase10-monitoring-alerts.md` (Phase 10); `work-reports/daily/2026-07-26-phase9-deployment.md` (Phase 9, deployment side-track) |

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
- [x] Passwordless email-link signup + forgot/reset password (Ch.12f, Ch.12i) — signup collects only email, no account exists until the emailed link is clicked at /complete-signup, which then sets a password; confirmed working end-to-end on live site 2026-07-28 (supersedes the 2026-07-27 verify-after-creation approach)
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
