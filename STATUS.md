# Current Status

*(Update this every time you stop working. Single source of truth for "where are we.")*

| Field | Value |
|---|---|
| **Active phase** | Phase 7 — Async Workers |
| **Last updated by** | Claude |
| **Last updated on** | 2026-07-25 |
| **Blocking issue, if any** | None — Phases 1 through 6 are all real-verified end to end. Phase 6's real Firebase/Firestore gap (flagged here previously) is now closed: the repo owner ran `tests/phase6_real_keys_smoke_test.py` with two real Firebase Auth users and real ID tokens, no dependency-override shortcuts — every isolation guarantee (independent workspaces/channels, no cross-leak in `GET /channels`, cross-user access correctly 403, unknown channel correctly 404) held up for real, on the first pass. The real run did surface two pre-existing bugs, both now fixed and confirmed with a follow-up real run: the Grammar Check was failing grammatically correct writing over style preferences, and the Copyright Check was flagging a script and its own description as "copying" each other for covering the same topic — neither was a Phase 6 bug, both live in Phase 4's `prompt_library.py` (full story in `phases/phase-04-langgraph-core-agents/PHASE.md`'s handoff notes). A final real run after both fixes passed clean on the first try, all four review gates green, zero retries. Only remaining open item across Phases 1-6: `backend/ai/rag/backfill.py` still hasn't been run against a real export from the old pipeline — low priority, no such export exists yet to test it against.
| **Next concrete action** | Begin Phase 7 — see `phases/phase-07-async-workers/PHASE.md`. (Side-track: Phase 9's CI/CD half is done independently — see below — pick up its remaining deploy-target task whenever.) |
| **Latest work report** | `work-reports/daily/2026-07-25-phase6-real-keys-verified.md` (today's real verification + the two prompt-quality bug fixes), `work-reports/daily/2026-07-25-phase6-multi-tenancy-done.md` (original Phase 6 build), `work-reports/daily/2026-07-25-phase5-real-keys-verified.md` and `work-reports/daily/2026-07-24-phase4-real-keys-verified.md` (earlier real-keys verification), and `work-reports/daily/2026-07-24-phase9-ci-cd-live.md` (independent side-track) |

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
