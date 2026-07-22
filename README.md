# AI CarryON

Autonomous Multi-Agent YouTube Operating System.

This repo is a **holder / scaffold** — the folder shape and phase briefs are already set up so that
whoever opens it next (including future-you) can go straight to their segment and start working,
with zero setup.

## Where to look

| I want to... | Go to |
|---|---|
| Understand *why* the system is designed this way | [`docs/AI-CarryON-Architecture-Document.html`](docs/AI-CarryON-Architecture-Document.html) (the SAD) |
| Understand *what to build next* and the full phase order | [`BUILD_GUIDE.md`](BUILD_GUIDE.md) |
| See where the project currently stands | [`STATUS.md`](STATUS.md) |
| Work on one specific phase/segment | [`phases/`](phases/) — each phase has its own self-contained `PHASE.md` |
| Log what I actually did this session | [`work-reports/`](work-reports/) — copy `TEMPLATE.md`, one file per session, never edited after the fact |

## How this repo is organized

- `docs/` — the SAD and the full Build Guide (reference copies, don't edit these — edit the root `BUILD_GUIDE.md` if the plan changes)
- `phases/phase-00-...` through `phases/phase-12-...` — one folder per build phase, each with a `PHASE.md` containing that phase's Goal, Depends On, Tasks, Definition of Done, and Handoff Notes, lifted directly from the Build Guide so it's readable on its own
- `backend/`, `frontend/`, `deployment/`, `tests/`, `docker/`, `.github/workflows/` — the actual code skeleton (Phase 0's folder shape); code lands here as each phase is built, regardless of which phase folder "owns" the task
- `.env.example` — every environment variable any phase needs; copy to `.env` and fill in as you go

## The rule

Whoever stops mid-phase, before stopping:
1. Ticks every checkbox actually finished in that phase's `PHASE.md`.
2. Writes 2–5 sentences in that phase's **Handoff Notes**.
3. Updates `STATUS.md`.
4. Adds one file to `work-reports/` for the session (copy `work-reports/TEMPLATE.md`).

Follow that and no handoff call is ever needed — just open your `PHASE.md` and continue.
