# Current Status

*(Update this every time you stop working. Single source of truth for "where are we.")*

| Field | Value |
|---|---|
| **Active phase** | Phase 8 — Scheduler |
| **Last updated by** | Claude |
| **Last updated on** | 2026-07-25 |
| **Blocking issue, if any** | Phase 7 (this repo's newest work) hasn't been exercised against real ElevenLabs/YouTube/ffmpeg — everything in `tests/phase7_async_workers_test.py` runs against faked TTS/upload calls and a faked `subprocess.run`, same convention as Phase 4/5's original fake-first test scripts before their real-keys smoke tests existed. `render_worker.py` does shell out to a REAL `ffmpeg` binary in production (not faked at the binary level, only in the test script) — a real local run needs `ffmpeg` installed (`brew install ffmpeg` on the Mac, already in `docker/Dockerfile` for the container). Phase 6's own blocking issue (real Firebase/Firestore end-to-end pass) is still open too — nothing in Phase 7 required it, but it's still worth doing before either phase is trusted beyond local dev. So: before trusting Phase 7 beyond local dev, run a real end-to-end pass with real `ELEVENLABS_API_KEY`, real `YOUTUBE_CLIENT_SECRETS_B64`/`YOUTUBE_TOKEN_B64`, real `CELERY_BROKER_URL` (Upstash's Redis-protocol connection string, not the REST one — see `app/workers/celery_app.py`'s module docstring), and a real `ffmpeg` binary — the same way Phases 3-5 already got theirs (a `phase7_real_keys_smoke_test.py`, not yet written, is the natural next step whenever real keys are available). |
| **Next concrete action** | Begin Phase 8 — see `phases/phase-08-scheduler/PHASE.md`. Worth a real-keys smoke test of Phase 7 first (see row above) — Phase 8's scheduled trigger is the thing that will actually call `enqueue_render` unattended for the first time, so it's better to already know the render chain works for real before wiring a cron job on top of it. |
| **Latest work report** | `work-reports/daily/2026-07-25-phase7-async-workers-done.md` (mainline) |

## Independent side-track: Phase 9 (CI/CD)

Built out of order on purpose — Phase 9 is the one phase the guide explicitly allows starting early ("or earlier ... recommended, don't wait"). Doesn't block or get blocked by Phase 4/5.

- [x] `docker/Dockerfile` — updated in Phase 7 to add `ffmpeg` + `fonts-dejavu-core` system packages
- [x] `.github/workflows/deploy.yml` — test + build + push to `ghcr.io` verified green end-to-end
- [ ] Deploy target decision (Cloud Run vs Railway) — still open, see `phases/phase-09-deployment/PHASE.md`. Phase 7 adds a second consideration to that decision: a worker container (`celery -A app.workers.celery_app worker`) needs to run continuously, unlike the API's request-driven scaling — factor that into whichever target gets picked.

## Prerequisites checklist

Copied from `BUILD_GUIDE.md` §2 — do these once, up front, regardless of which phase you're on:

- [x] GitHub repo created (private is fine to start)
- [x] Firebase project created — console.firebase.google.com (Spark/free plan)
- [x] Upstash account for Redis — upstash.com (free tier, REST-based) *(Phase 7: also its Redis-protocol `rediss://` connection string, same instance, used as Celery's broker/backend)*
- [x] Qdrant Cloud account — cloud.qdrant.io (free 1GB cluster) *(real cluster created and verified — see Phase 5's real-keys work report)*
- [x] Gemini API key — aistudio.google.com
- [ ] (Optional, can defer) Google Cloud project for Cloud Run / Cloud Tasks / Cloud Scheduler — Phase 7 ended up NOT needing Cloud Tasks (see `phases/phase-07-async-workers/PHASE.md`'s own handoff note on why Celery+Redis was chosen instead); still open for Phase 9's deploy-target decision and Phase 8's scheduler
- [ ] ElevenLabs API key for voice — *(no longer optional as of Phase 7 — `voice_worker.py` needs `ELEVENLABS_API_KEY` for real runs; the code runs fine without it in tests via the fake, per the Blocking Issue row above)*
- [ ] YouTube Data API OAuth credentials — console.cloud.google.com *(needed for `upload_worker.py`'s real runs — `YOUTUBE_CLIENT_SECRETS_B64` / `YOUTUBE_TOKEN_B64`, base64-encoded per the old pipeline's pattern, see `integrations/youtube/client.py`)*
- [x] Python 3.11+
- [x] Groq API key — console.groq.com *(this checklist predates Phase 4; add it to BUILD_GUIDE.md §2 next time it's edited)*
- [x] Serper.dev API key — serper.dev *(same note — used for the Research Agent's web search, not originally listed here either)*
- [ ] Node 20+
- [ ] Docker Desktop (only needed from Phase 9 onward)
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
| 9 — Deployment | `phases/phase-09-deployment/` | 8 (or earlier) |
| 10 — Monitoring & Alerts | `phases/phase-10-monitoring-alerts/` | 9 |
| 11 — Frontend Dashboard | `phases/phase-11-frontend-dashboard/` | 6 min, ideally 10 |
| 12 — Learning Agent | `phases/phase-12-learning-agent/` | 11 + real analytics data |
