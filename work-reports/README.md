# Work Reports

A running log of actual work — separate from `phases/*/PHASE.md`.

**The difference between this and a phase's Handoff Notes:**
- `phases/*/PHASE.md` → Handoff Notes = a snapshot for whoever picks up *that phase* next. Gets overwritten/updated as the phase progresses.
- `work-reports/` → a permanent, append-only history. Never edited after the fact. Answers "what actually happened on this project, over time" — useful for your own memory, a client update, or a changelog later.

## Three tiers

| Folder | Cadence | Use for |
|---|---|---|
| `daily/` | Every session you stop | The raw diary — what you built, what broke, next step. Copy `daily/TEMPLATE.md`. |
| `weekly/` | Once a week (or whenever a natural chunk of work closes) | A short roll-up of that week's `daily/` entries — what shipped, what's still stuck, what changed direction. |
| `milestones/` | Once per phase completed (or major decision) | The durable record: "Phase 4 done", "switched from Celery to Cloud Tasks", etc. This is what you'd show someone who wasn't there for the daily grind. |

Not every day needs a weekly entry, and not every week needs a milestone. Skip the tiers that don't apply — the point is a report exists at whatever granularity actually happened, not that all three are filled in lockstep.

## How to use it

**Daily**, every time you finish a work session:
```
work-reports/daily/YYYY-MM-DD-short-slug.md
```
e.g. `work-reports/daily/2026-07-22-phase1-firestore-rules.md` — copy `daily/TEMPLATE.md`.

**Weekly**, roughly once a week:
```
work-reports/weekly/YYYY-WW-summary.md
```
e.g. `work-reports/weekly/2026-W30-summary.md` — a few sentences summarizing that week's `daily/` files, not a re-copy of them.

**Milestones**, when a phase (or a big decision) is done:
```
work-reports/milestones/YYYY-MM-DD-phaseN-done.md
```
e.g. `work-reports/milestones/2026-07-25-phase1-done.md`.

Don't edit old reports — if something turns out to be wrong, note the correction in a new report instead.

Then, in the same commit, also update `STATUS.md` and the relevant phase's `PHASE.md` — the work report is the diary, `STATUS.md`/`PHASE.md` are the current-state files. Keep them in sync.

## Index

*(Add a row here each time you add a report — newest first.)*

| Date | Tier | Phase | Summary | File |
|---|---|---|---|---|
| 2026-07-24 | daily | Phase 4 | Real-keys verification: caught + fixed retired Gemini models, swallowed fallback errors | `daily/2026-07-24-phase4-real-keys-verified.md` |
| 2026-07-24 | milestone | Phase 4 | Full LangGraph pipeline (9 agents) shipped, verified against faked externals | `milestones/2026-07-24-phase4-done.md` |
| 2026-07-24 | daily | Phase 4 | LangGraph core agents built and tested; real API keys not yet exercised | `daily/2026-07-24-phase4-langgraph-core-agents-done.md` |
| 2026-07-23 | milestone | Phase 3 | Redis client + real rate limiter, verified against fake Upstash | `milestones/2026-07-23-phase3-done.md` |
| 2026-07-23 | daily | Phase 3 | Redis client + real rate limiter shipped and tested | `daily/2026-07-23-phase3-redis-upstash-done.md` |
| 2026-07-22 | daily | Phase 0 | Scaffold restructured, pushed to GitHub | `daily/2026-07-22-phase0-repo-live.md` |
