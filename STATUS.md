# Current Status

*(Update this every time you stop working. Single source of truth for "where are we.")*

| Field | Value |
|---|---|
| **Active phase** | Phase 6 — Multi-Tenancy: Channel Brain / Factory |
| **Last updated by** | Claude |
| **Last updated on** | 2026-07-24 |
| **Blocking issue, if any** | Phase 5's RAG pipeline is only verified with Qdrant and Gemini's embedding endpoint faked in-process — real network egress to `generativelanguage.googleapis.com` and a real Qdrant Cloud cluster hasn't been exercised from this environment yet. Not blocking Phase 6, but before trusting retrieval quality: (1) run a real research request and confirm Gemini's `embed_content` response shape matches what `integrations/gemini/client.py`'s `embed()` expects, (2) run `backend/ai/rag/backfill.py` against a real export from the *old* pipeline (not the illustrative `sample_backfill.json`), (3) create the Qdrant Cloud cluster and confirm `ensure_collections()` runs clean against it. **Resolved since this was written:** Phase 4's real-Gemini/Groq/Serper gap and Phase 3's real-Upstash gap are both closed — the repo owner ran `tests/phase4_real_keys_smoke_test.py` for real on 2026-07-24 (a real Upstash DB, real Gemini/Groq/Serper keys), which also caught and fixed two real bugs (retired `gemini-1.5-*` model names, a fallback-chain error that was hiding the real failure). See `phases/phase-04-langgraph-core-agents/PHASE.md`'s handoff notes for the full story.
| **Next concrete action** | Begin Phase 6 — see `phases/phase-06-multi-tenancy-channel-factory/PHASE.md`. (Side-track: Phase 9's CI/CD half is done independently — see below — pick up its remaining deploy-target task whenever.) |
| **Latest work report** | `work-reports/daily/2026-07-24-phase5-qdrant-rag-done.md` (mainline) and `work-reports/daily/2026-07-24-phase9-ci-cd-live.md` (independent side-track) |

## Independent side-track: Phase 9 (CI/CD)

Built out of order on purpose — Phase 9 is the one phase the guide explicitly allows starting early ("or earlier ... recommended, don't wait"). Doesn't block or get blocked by Phase 4/5.

- [x] `docker/Dockerfile`
- [x] `.github/workflows/deploy.yml` — test + build + push to `ghcr.io` verified green end-to-end
- [ ] Deploy target decision (Cloud Run vs Railway) — still open, see `phases/phase-09-deployment/PHASE.md`

## Prerequisites checklist

Copied from `BUILD_GUIDE.md` §2 — do these once, up front, regardless of which phase you're on:

- [x] GitHub repo created (private is fine to start)
- [x] Firebase project created — console.firebase.google.com (Spark/free plan)
- [x] Upstash account for Redis — upstash.com (free tier, REST-based)
- [ ] Qdrant Cloud account — cloud.qdrant.io (free 1GB cluster) *(still no real cluster created/tested against — Phase 5 built and tested the whole RAG pipeline against a faked Qdrant; see this file's Blocking issue row)*
- [x] Gemini API key — aistudio.google.com
- [ ] (Optional, can defer) Google Cloud project for Cloud Run / Cloud Tasks / Cloud Scheduler
- [ ] (Optional, can defer) ElevenLabs API key for voice
- [ ] YouTube Data API OAuth credentials — console.cloud.google.com
- [ ] Python 3.11+
- [x] Groq API key — console.groq.com *(this checklist predates Phase 4; add it to BUILD_GUIDE.md §2 next time it's edited)*
- [x] Serper.dev API key — serper.dev *(same note — used for the Research Agent's web search, not originally listed here either)*
- [ ] Node 20+
- [ ] Docker Desktop (only needed from Phase 9 onward)

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
