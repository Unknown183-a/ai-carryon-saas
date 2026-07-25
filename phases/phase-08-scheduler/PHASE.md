<!-- Self-contained phase brief. Companion docs: ../../BUILD_GUIDE.md (full build order) and ../../docs/architecture/AI-CarryON-Architecture.html (the why). -->

## Phase 8 — Scheduler
*(SAD reference: Chapter 16 — Cloud Scheduler)*

**Goal:** channels generate videos on their own schedule without a human triggering anything.

**Depends on:** Phase 7.

**Tasks:**
- [x] Cloud Scheduler job (or cron-triggered endpoint if deferring GCP) hitting `POST /internal/scheduler/run-due-channels` — built the cron-triggered endpoint (GCP deferred, same as Phase 7's Cloud-Tasks-vs-Celery choice deferred GCP); `.github/workflows/scheduler.yml` is the interim cron trigger, a documented no-op until Phase 9 picks a deploy target and `SCHEDULER_URL`/`INTERNAL_SCHEDULER_TOKEN` repo secrets exist
- [x] That endpoint queries Firestore for channels whose `schedules` document says they're due, and calls Phase 6's generate endpoint for each — `tenant_platform/scheduler/scheduler_service.list_due_channel_ids` + `app/services/generation_service.run_generation` (the same function `POST /channels/{id}/generate` now calls too, extracted in this phase specifically so the two callers can't drift apart)
- [x] Reuse the existing 9 AM IST Railway scheduler's logic/timing as the reference implementation — don't redesign the scheduling rules from scratch — `tenant_platform/scheduler/schedule_rules.py`'s `DEFAULT_TIME_OF_DAY = "09:00"` / `DEFAULT_TIMEZONE = "Asia/Kolkata"`; see that module's own docstring for what "reuse" means precisely, given the old Railway pipeline's actual source isn't part of this repo
- [x] Confirm Scheduler-triggered requests pass through the Permission Check (Ch.12e) using a system role token, not a user JWT — `tenant_platform/security/permissions.py`'s `require_system_token`, proven by `tests/phase8_scheduler_test.py`'s Test 3 (correct system token + **no** `Authorization` header at all still succeeds)

**Definition of Done:** a channel with a due schedule generates a video with zero manual intervention, observed over at least one real scheduled trigger (not just a manual test call).

**Handoff Notes:**
> Worth being precise about what "observed over at least one real scheduled trigger" means here, same convention Phase 7's handoff used for "verified structurally" vs "verified functionally":
>
> **Functionally verified, end-to-end, in a unit test**: `tests/phase8_scheduler_test.py` (30 checks) proves a channel whose schedule is due gets a real pipeline run — script, SEO, review, and a real (eager-mode, faked-externals) render chain — triggered by `POST /internal/scheduler/run-due-channels` alone, with zero `Authorization` header and zero direct `/generate` call from the test. That's "zero manual intervention" and "not just a manual test call" in every sense a unit test can stage — same honest boundary Phase 7's own handoff drew around its broker-level retry claim.
>
> **NOT yet observed**: an actual GitHub Actions cron firing against a real, deployed instance on its own 30-minute timer. That can't happen until Phase 9 picks a deploy target (Cloud Run vs Railway is still open — see `STATUS.md`) and the app has a real `SCHEDULER_URL`. `.github/workflows/scheduler.yml` is wired and ready — same "no-op until secrets exist" shape `deploy.yml`'s own deploy job already used for its undecided target — but has never actually fired against anything real. **Next concrete action if you pick this phase back up post-Phase-9**: add the two repo secrets, watch one real 30-minute cron tick actually hit the deployed endpoint and produce a real render, and only then treat this phase's Definition of Done as fully closed (not just functionally proven).
>
> Design decisions made along the way, in case they're worth revisiting:
> - `upload_schedule`'s five recognized values (`1_per_day`/`daily`, `5_per_week`, `3_per_week`, `1_per_week`) all reuse the same 09:00 IST time-of-day, differing only in which weekdays they run — an unrecognized value falls back to daily rather than silently never running (see `schedule_rules.py`'s own comment on why "runs more than expected" beats "never runs" as a failure mode).
> - A channel whose schedule is due but whose `status` isn't `"ready"` still gets its `next_run_at` advanced (not left due forever) — otherwise it would look "due" on every single poll until someone manually fixes it, indistinguishable from a retry storm from the outside. See `tests/phase8_scheduler_test.py`'s Test 5.
> - One channel's run failing (an exception from `run_generation`) is caught and reported in that channel's own `results` entry, never raised — a bad channel config must not stop nine other due channels' 9 AM IST run from happening. Not explicitly covered by a test in this phase (would need a way to force `run_generation` to raise for exactly one channel without breaking the fake LLM setup for the others) — worth adding if this phase is revisited.
> - Storage is the same known, deliberate gap Phase 7's handoff already documented (`app/workers/storage.py`) — nothing in this phase changes that; a scheduled run goes through the identical worker chain a manual run does.

---
