# Phases index

Each subfolder here is one build phase, fully self-contained: open its `PHASE.md` and you have
the Goal, Depends On, Tasks, Definition of Done, and Handoff Notes for that segment, without
needing to read anything else first (though `../docs/AI-CarryON-Architecture-Document.html` has
the full "why" if you want it).

Build order matters — see the "Depends on" line in each `PHASE.md`, or the table in `../STATUS.md`.

| # | Phase |
|---|---|
| 00 | Repo & Skeleton |
| 01 | Firebase Auth + Firestore |
| 02 | FastAPI Gateway (shell only) |
| 03 | Redis (Upstash) |
| 04 | LangGraph, single hardcoded channel |
| 05 | Qdrant + RAG |
| 06 | Multi-Tenancy: Channel Brain, Workspace, Channel Factory |
| 07 | Async Workers (Render, Voice, Upload) |
| 08 | Scheduler |
| 09 | Deployment |
| 10 | Monitoring & Alerts |
| 11 | Frontend Dashboard |
| 12 | Learning Agent |
