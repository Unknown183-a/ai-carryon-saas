# Work Reports

A running log of actual work sessions — separate from `phases/*/PHASE.md`.

**The difference between this and a phase's Handoff Notes:**
- `phases/*/PHASE.md` → Handoff Notes = a snapshot for whoever picks up *that phase* next. Gets overwritten/updated as the phase progresses.
- `work-reports/` → a permanent, append-only history of *sessions*. Never edited after the fact. Answers "what actually happened on this project, session by session" — useful for your own memory, a client update, or a changelog later.

## How to use it

Every time you finish a work session (or stop for the day), add one file:

```
work-reports/YYYY-MM-DD-short-slug.md
```

e.g. `work-reports/2026-07-22-phase1-firestore-rules.md`

Copy `TEMPLATE.md`, fill it in, done. Don't edit old reports — if something from an old report turns out to be wrong, note the correction in a new report instead.

Then, in one line, also update `STATUS.md` and the relevant phase's `PHASE.md` — the work report is the diary, `STATUS.md`/`PHASE.md` are the current-state files. Keep all three in sync in the same commit.

## Index

*(Add a row here each time you add a report — newest first.)*

| Date | Phase | Summary | File |
|---|---|---|---|
| _(none yet)_ | | | |
