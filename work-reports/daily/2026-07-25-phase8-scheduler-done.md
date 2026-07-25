# Work Report — 2026-07-25

**Phase worked on:** Phase 8 — Scheduler
**Author:** Claude
**Time spent:** ~1 session

## What I built / did

- `tenant_platform/scheduler/schedule_rules.py` — pure timing logic: default 09:00
  IST, per-`upload_schedule` weekday sets, `compute_next_run_at`, `is_due`.
- `tenant_platform/scheduler/scheduler_service.py` — `register_schedule`,
  `list_due_channel_ids`, `mark_schedule_ran`, all backed by a new `schedules`
  Firestore collection (`app/database/firestore_collections.py`).
- Extracted the LangGraph pipeline invocation out of `channels.py`'s `generate_video`
  into `app/services/generation_service.py`'s `run_generation`, shared by both the
  human-triggered `/generate` route and the new scheduler route.
- `tenant_platform/security/permissions.py`'s `require_system_token` — the Ch.16
  "system role token, not user JWT" check, via `X-Internal-Scheduler-Token` +
  `hmac.compare_digest`.
- `app/api/routers/internal_scheduler.py` — `POST /internal/scheduler/run-due-channels`:
  loops due channels, runs each, isolates per-channel failures, always advances that
  channel's schedule afterward.
- Wired the previously-stubbed "Register Scheduler" step into
  `tenant_platform/factory/factory.py` — every new channel now gets a schedule doc at
  creation time.
- `.github/workflows/scheduler.yml` — the interim cron trigger (GCP Cloud Scheduler
  deferred, same as Phase 7 deferred Cloud Tasks), a documented no-op until Phase 9
  picks a deploy target and repo secrets exist.
- `docs/decisions/0002-scheduler-system-auth.md` — recorded the system-token-vs-widened-
  membership-check and Firestore-schedule-doc design choices.
- `tests/phase8_scheduler_test.py` — new, 30 checks.
- Updated `tests/phase6_multi_tenancy_test.py`'s tripwire test to patch
  `get_graph` at its new location (`generation_service`, not `channels` anymore) —
  necessary because of the `run_generation` extraction, not scope creep.

## What's now working (proof, not vibes)

- `python3 tests/phase8_scheduler_test.py` → `30 passed, 0 failed`, covering:
  schedule-timing math in isolation; a channel created through the real Factory getting
  a real schedule doc; the internal route rejecting no-token (401) and wrong-token
  (403) and succeeding on a correct token with **zero** `Authorization` header; a due
  channel getting a full real pipeline run (script → SEO → review → render task)
  triggered with no direct `/generate` call anywhere in the test, its schedule
  advancing afterward so an immediate re-poll does not re-trigger it; a non-`"ready"`
  channel being skipped but still having its schedule advanced.
- Full existing suite still green after the `channels.py` refactor:
  `phase3_redis_ratelimit_test.py`, `phase4_langgraph_test.py`,
  `phase5_qdrant_rag_test.py` (13/13), `phase6_multi_tenancy_test.py` (23/23, after the
  `get_graph` patch-location fix), `phase7_async_workers_test.py` (40/40).

## What broke / what I couldn't finish

- The real-scheduled-trigger half of Phase 8's Definition of Done ("observed over at
  least one real scheduled trigger, not just a manual test call") is NOT done — there's
  no live deployment yet for `.github/workflows/scheduler.yml` to actually hit. This is
  correctly blocked on Phase 9's still-open deploy-target decision, not something Phase
  8 itself could have closed out. See `phases/phase-08-scheduler/PHASE.md`'s Handoff
  Notes for the exact line drawn between "functionally verified" and "observed live."
- One channel's `run_generation` failure being caught-and-reported (not raised) is
  implemented but not covered by its own test — would need a way to force a failure for
  exactly one channel among several without breaking the shared fake-LLM setup. Worth
  adding if this phase is revisited.

## Decisions made (and why)

- System role token (shared secret + `hmac.compare_digest`) over widening
  `require_channel_access`'s membership check for a synthetic "scheduler user" — keeps
  Ch.12e's workspace-isolation guarantee unconditional rather than carving an exception
  into it. Full reasoning + trade-offs in `docs/decisions/0002-scheduler-system-auth.md`.
- `next_run_at <= now` filtered in Python after a single-clause Firestore query, not as
  a second inequality clause — matches every existing query in
  `firestore_collections.py`.
- A channel that isn't due yet just isn't in `run-due-channels`' results at all — not
  listed as `"skipped"` with a reason, unlike a due-but-not-ready channel. Kept the
  distinction because "not due" is the expected steady state for the vast majority of
  channels on every poll, not a noteworthy event.

## Next concrete step

Begin Phase 9 (Deployment); once a target's picked and live, add
`SCHEDULER_URL`/`INTERNAL_SCHEDULER_TOKEN` repo secrets and watch one real cron tick
close the remaining gap in this phase's Definition of Done.

## Checkboxes ticked this session

- [x] Cloud Scheduler job (or cron-triggered endpoint if deferring GCP) hitting `POST /internal/scheduler/run-due-channels`
- [x] That endpoint queries Firestore for channels whose `schedules` document says they're due, and calls Phase 6's generate endpoint for each
- [x] Reuse the existing 9 AM IST Railway scheduler's logic/timing as the reference implementation — don't redesign the scheduling rules from scratch
- [x] Confirm Scheduler-triggered requests pass through the Permission Check (Ch.12e) using a system role token, not a user JWT
