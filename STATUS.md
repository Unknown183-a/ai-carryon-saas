# Current Status

*(Update this every time you stop working. Single source of truth for "where are we.")*

| Field                      | Value                                                          |
| -------------------------- | -------------------------------------------------------------- |
| **Active phase**           | Phase 9 — Deployment (code/config done, GCP account setup pending) |
| **Last updated by**        | Amit                                                           |
| **Last updated on**        | 2026-07-26                                                     |
| **Blocking issue, if any** | Needs GCP service account + repo secrets (`GCP_SA_KEY`, `GCP_PROJECT_ID`) created manually — see `docs/deployment/README.md` |
| **Next concrete action**   | Create the GCP service account per the runbook, add the two repo secrets, then merge to `main` to trigger the first real Cloud Run deploy |
| **Latest work report**     | `work-reports/daily/2026-07-26-phase9-deployment.md`           |

## Prerequisites checklist

Copied from `BUILD_GUIDE.md` §2 — do these once, up front, regardless of which phase you're on:

- [ ] GitHub repo created (private is fine to start)
- [ ] Firebase project created — console.firebase.google.com (Spark/free plan)
- [ ] Upstash account for Redis — upstash.com (free tier, REST-based)
- [ ] Qdrant Cloud account — cloud.qdrant.io (free 1GB cluster)
- [ ] Gemini API key — aistudio.google.com
- [ ] Google Cloud project for Cloud Run — now required, not optional, as of Phase 9
- [ ] (Optional, can defer) ElevenLabs API key for voice
- [ ] YouTube Data API OAuth credentials — console.cloud.google.com
- [ ] Python 3.11+
- [ ] Node 20+
- [x] Docker Desktop

## Phase index

| Phase                                      | Folder                                           | Depends on               |
| ------------------------------------------ | ------------------------------------------------ | ------------------------ |
| 0 — Repo & Skeleton                        | `phases/phase-00-repo-skeleton/`                 | —                        |
| 1 — Firebase Auth + Firestore              | `phases/phase-01-firebase-auth-firestore/`       | 0                        |
| 2 — FastAPI Gateway (shell)                | `phases/phase-02-fastapi-gateway/`               | 1                        |
| 3 — Redis (Upstash)                        | `phases/phase-03-redis-upstash/`                 | 2                        |
| 4 — LangGraph, single hardcoded channel    | `phases/phase-04-langgraph-core-agents/`         | 3                        |
| 5 — Qdrant + RAG                           | `phases/phase-05-qdrant-rag/`                    | 4                        |
| 6 — Multi-Tenancy: Channel Brain / Factory | `phases/phase-06-multi-tenancy-channel-factory/` | 5, 3                     |
| 7 — Async Workers                          | `phases/phase-07-async-workers/`                 | 6                        |
| 8 — Scheduler                              | `phases/phase-08-scheduler/`                     | 7                        |
| 9 — Deployment                             | `phases/phase-09-deployment/`                    | 8 (or earlier)           |
| 10 — Monitoring & Alerts                   | `phases/phase-10-monitoring-alerts/`             | 9                        |
| 11 — Frontend Dashboard                    | `phases/phase-11-frontend-dashboard/`            | 6 min, ideally 10        |
| 12 — Learning Agent                        | `phases/phase-12-learning-agent/`                | 11 + real analytics data |
