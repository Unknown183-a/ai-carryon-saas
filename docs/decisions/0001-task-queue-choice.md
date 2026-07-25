# 0001 — Task queue: Celery + Redis over Cloud Tasks

**Status:** Decided, Phase 7 (2026-07-25)

**Context**

Phase 7's brief (`phases/phase-07-async-workers/PHASE.md`, SAD Ch.15) left the task
queue as an open choice: Cloud Tasks (if already on GCP) or Celery + Redis broker.

**Decision**

Celery + Redis, reusing the exact same Upstash instance Phase 3 already provisioned —
its plain Redis-protocol (`rediss://`) connection string, not the REST API Phase 3's
`app/core/redis_client.py` uses for caching. Same database, two protocols; no second
Redis instance, no second bill. See `backend/app/workers/celery_app.py`'s module
docstring for the exact mechanics.

**Why**

- **Nothing new to provision.** This project isn't committed to GCP — Phase 9's deploy
  target (Cloud Run vs Railway) is still an open decision as of this writing. Cloud Tasks
  would mean standing up a GCP project *specifically* to unblock Phase 7, ahead of that
  decision being made for unrelated reasons.
- **Redis already existed.** Phase 3 provisioned Upstash for caching; Celery's Redis
  broker/backend transport works against that same instance immediately.
- **Retry semantics map cleanly.** Cloud Tasks' at-least-once delivery + automatic retry
  on a 5xx has a direct Celery equivalent: `task_acks_late` + `task_reject_on_worker_lost`
  (broker-level — survives a worker process dying mid-job) plus each task's own
  `autoretry_for`/`retry_backoff` (task-level — survives the task itself failing). Neither
  mechanism is Cloud-Tasks-specific; both are documented and tested in
  `tests/phase7_async_workers_test.py`.

**Trade-off, stated plainly**

Cloud Tasks would have been the better long-term fit if this project were already
committed to GCP for Phase 9 — it's a managed service with less to operate than a
self-run Celery worker process. Choosing Celery+Redis now means Phase 9's deploy-target
decision picks up a second consideration it didn't have before: a worker container needs
to run continuously (unlike the API's request-driven scaling), regardless of which
target is picked. Noted in `STATUS.md`'s Phase 9 side-track row.

**Revisit if:** Phase 9 ends up choosing Cloud Run *and* GCP becomes the committed
platform for other reasons — at that point Cloud Tasks becomes a fair re-litigation,
not before.
