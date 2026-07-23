# Current Status

*(Update this every time you stop working. Single source of truth for "where are we.")*

| Field | Value |
|---|---|
| **Active phase** | Phase 4 — LangGraph, single hardcoded channel |
| **Last updated by** | Claude |
| **Last updated on** | 2026-07-23 |
| **Blocking issue, if any** | Phase 3's rate limiter is only verified against a fake in-memory Upstash server — no real Upstash account exists yet (see prerequisites checklist below). Not blocking Phase 4, but re-verify against real Upstash before relying on it in production. |
| **Next concrete action** | Begin Phase 4 — see `phases/phase-04-langgraph-core-agents/PHASE.md` |
| **Latest work report** | `work-reports/daily/2026-07-23-phase3-redis-upstash-done.md` |

## Prerequisites checklist

Copied from `BUILD_GUIDE.md` §2 — do these once, up front, regardless of which phase you're on:

- [ ] GitHub repo created (private is fine to start)
- [ ] Firebase project created — console.firebase.google.com (Spark/free plan)
- [ ] Upstash account for Redis — upstash.com (free tier, REST-based)
- [ ] Qdrant Cloud account — cloud.qdrant.io (free 1GB cluster)
- [ ] Gemini API key — aistudio.google.com
- [ ] (Optional, can defer) Google Cloud project for Cloud Run / Cloud Tasks / Cloud Scheduler
- [ ] (Optional, can defer) ElevenLabs API key for voice
- [ ] YouTube Data API OAuth credentials — console.cloud.google.com
- [ ] Python 3.11+
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
