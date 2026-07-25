# 0002 — Scheduler: system-token endpoint + Firestore-stored per-channel schedules

**Status:** Decided, Phase 8 (2026-07-25)

**Context**

Phase 8's brief (`phases/phase-08-scheduler/PHASE.md`, SAD Ch.16) left two things open:
how a Scheduler-triggered request proves it's allowed to trigger every channel's
pipeline without being a member of every workspace, and where "is this channel due
right now" actually gets decided — GCP's Cloud Scheduler was explicitly deferred, same
as Phase 7 deferred Cloud Tasks (see `0001-task-queue-choice.md`).

**Decision**

1. **A shared-secret system token, not a per-workspace exception.** `POST
   /internal/scheduler/run-due-channels` is gated by `require_system_token`
   (`tenant_platform/security/permissions.py`) — a `X-Internal-Scheduler-Token` header
   checked with `hmac.compare_digest` against `INTERNAL_SCHEDULER_TOKEN` — instead of
   widening `require_channel_access`'s workspace-membership check to make an exception
   for a "scheduler user." The alternative (a real Firebase user representing the
   Scheduler, added as a member of every workspace) would have made Ch.12e's isolation
   guarantee conditionally true instead of always true — worse for a guarantee whose
   entire value is being unconditional.
2. **Schedules live in Firestore, one doc per channel, queried and filtered in Python.**
   `schedules/{channel_id}` docs store `enabled` + `next_run_at`; `list_due_channel_ids`
   fetches every enabled doc with one equality `.where()` clause, then filters
   `next_run_at <= now` in Python rather than as a second Firestore inequality clause.
   Matches every other query in `app/database/firestore_collections.py` (see that
   file's own module docstring on why every caller goes through it, and why the
   project's Firestore access layer has stayed single-clause throughout).
3. **A single shared `run_generation` function, not two separate pipeline-invocation
   code paths.** Extracted out of `app/api/routers/channels.py` into
   `app/services/generation_service.py` specifically because PHASE.md's task list says
   the Scheduler "calls Phase 6's generate endpoint for each" — the safest way to
   guarantee a Scheduler-triggered run and a human-triggered run can never quietly
   diverge in behavior is for them to literally be the same function call, not two
   handlers kept in sync by hand.

**Why**

- No new GCP dependency, same reasoning as `0001`: this project isn't committed to GCP
  yet, and Cloud Scheduler would mean provisioning ahead of Phase 9's still-open
  deploy-target decision, for a phase that doesn't strictly need it.
- A cron-triggered HTTP endpoint has an identical shape to what Cloud Scheduler would
  call anyway (`POST` a URL, expect 2xx) — swapping the trigger mechanism later (Cloud
  Scheduler hitting the same deployed endpoint) needs zero code changes here, only a
  Cloud Scheduler job pointed at the same route this phase already built.

**Trade-off, stated plainly**

A single shared static secret is coarser-grained than Cloud Scheduler's native
service-account identity (OIDC token, audience-checked, individually revocable) would
have been — anyone with `INTERNAL_SCHEDULER_TOKEN` can trigger every channel's
pipeline, and rotating it means updating it in exactly one place (whichever secret
store Phase 9's deploy target uses) rather than revoking one compromised identity among
several. Acceptable for a single-instance deployment with one trusted caller (the cron
job itself); worth revisiting if this project ever needs more than one system caller
with different privileges.
