# Current Status

*(Update this every time you stop working. Single source of truth for "where are we.")*

| Field | Value |
|---|---|
| **Active phase** | Phase 7 — Async Workers |
| **Last updated by** | Claude |
| **Last updated on** | 2026-07-25 |
| **Blocking issue, if any** | Phase 6 (this repo's newest work) hasn't been exercised against real Firebase/Firestore — everything in `tests/phase6_multi_tenancy_test.py` runs against a faked Firestore double. Phases 3, 4, and 5 are now closed out for real, though: the repo owner created real Upstash and Qdrant Cloud accounts and ran both `tests/phase4_real_keys_smoke_test.py` and `tests/phase5_real_keys_smoke_test.py` for real on 2026-07-24/25 — real Gemini/Groq/Serper calls, real Redis, real Qdrant Cloud (embedding, collection creation, a real pipeline run, a real point landing in Qdrant's `research` collection with correct metadata). That work surfaced and fixed three real bugs along the way: two retired model names (`gemini-1.5-flash`/`gemini-1.5-pro` → the `-latest` aliases; `gemini-embedding-001` → `gemini-embedding-2`) and a Qdrant Cloud payload-index requirement that took three attempts to actually fix (see `phases/phase-05-qdrant-rag/PHASE.md`'s handoff for the full debugging story). Only remaining open item from Phase 5's original three: `backend/ai/rag/backfill.py` still hasn't been run against a real export from the old pipeline (low priority, no such export exists yet). So: before trusting Phase 6 beyond local dev, run a real end-to-end pass — real `.env`, real Firebase project, `POST /workspaces` → `POST /channels` → `POST /channels/{id}/generate` — the same way Phases 3-5 already got theirs.
| **Next concrete action** | Begin Phase 7 — see `phases/phase-07-async-workers/PHASE.md`. Worth the real Firebase/Firestore smoke test above first, given how much has landed since Phase 3's Firestore work was last touched for real. (Side-track: Phase 9's CI/CD half is done independently — see below — pick up its remaining deploy-target task whenever.) |
| **Latest work report** | `work-reports/daily/2026-07-25-phase6-multi-tenancy-done.md` (mainline), `work-reports/daily/2026-07-25-phase5-real-keys-verified.md` and `work-reports/daily/2026-07-24-phase4-real-keys-verified.md` (real-keys verification), and `work-reports/daily/2026-07-24-phase9-ci-cd-live.md` (independent side-track) |

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
- [x] Qdrant Cloud account — cloud.qdrant.io (free 1GB cluster) *(real cluster created and verified — see Phase 5's real-keys work report)*
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
