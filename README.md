# AI CarryON

Autonomous Multi-Agent YouTube Operating System.

This repo is a **holder / scaffold** — the folder shape and phase briefs are already set up so that
whoever opens it next (including future-you) can go straight to their segment and start working,
with zero setup.

## Current Phase

*(Kept in sync with `STATUS.md` — that file is the source of truth; this is just a glance.)*

- [x] Phase 00 — Repo & Skeleton
- [x] Phase 01 — Firebase Auth + Firestore
- [x] Phase 02 — FastAPI Gateway
- [x] Phase 03 — Redis (Upstash)
- [ ] Phase 04 — LangGraph, single hardcoded channel
- [ ] Phase 05 — Qdrant + RAG
- [ ] Phase 06 — Multi-Tenancy
- [ ] Phase 07 — Async Workers
- [ ] Phase 08 — Scheduler
- [ ] Phase 09 — Deployment
- [ ] Phase 10 — Monitoring & Alerts
- [ ] Phase 11 — Frontend Dashboard
- [ ] Phase 12 — Learning Agent

**Progress**

```
Architecture   ██████████ 100%
Backend        ███░░░░░░░  25%   (auth + gateway + real rate limiting; no agents yet)
Frontend       ░░░░░░░░░░   0%
Workers        ░░░░░░░░░░   0%
```

## Where to look

| I want to... | Go to |
|---|---|
| Understand *why* the system is designed this way | [`docs/architecture/AI-CarryON-Architecture.html`](docs/architecture/AI-CarryON-Architecture.html) (the SAD) |
| Understand *what to build next* and the full phase order | [`BUILD_GUIDE.md`](BUILD_GUIDE.md) — the single working copy, edit this if the plan changes |
| See where the project currently stands | [`STATUS.md`](STATUS.md) |
| Work on one specific phase/segment | [`phases/`](phases/) — each phase has its own self-contained `PHASE.md` |
| Log what I actually did | [`work-reports/`](work-reports/) — `daily/` each session, `weekly/` roll-ups, `milestones/` on phase completion |

## How this repo is organized

- `docs/architecture/` — the SAD (one copy, reference only — don't edit, it explains *why*). `docs/api/`, `docs/decisions/`, `docs/deployment/`, `docs/diagrams/` are optional, fill in as needed (see each folder's `README.md`).
- `BUILD_GUIDE.md` (root) — the one living build-order document; edit this if scope/order changes, then re-derive `phases/*/PHASE.md` from it
- `phases/phase-00-...` through `phases/phase-12-...` — one folder per build phase, each with a `PHASE.md` containing that phase's Goal, Depends On, Tasks, Definition of Done, and Handoff Notes
- `backend/` — organized by **responsibility**, not technology: `app/`, `ai/`, `platform/`, `integrations/`, `configs/`. See `backend/README.md` for the full map, the two "which folder for what" clarifications, and the folder-count guardrail.
- `frontend/`, `deployment/`, `tests/`, `docker/`, `.github/workflows/` — the rest of Phase 0's skeleton; code lands here as each phase is built
- `.env.example` — every environment variable any phase needs; copy to `.env` and fill in as you go

## The rule

Whoever stops mid-phase, before stopping:
1. Ticks every checkbox actually finished in that phase's `PHASE.md`.
2. Writes 2–5 sentences in that phase's **Handoff Notes**.
3. Updates `STATUS.md` (and the Current Phase checklist above, if a phase just finished).
4. Adds one file to `work-reports/daily/` for the session (copy `work-reports/daily/TEMPLATE.md`).

Follow that and no handoff call is ever needed — just open your `PHASE.md` and continue.
