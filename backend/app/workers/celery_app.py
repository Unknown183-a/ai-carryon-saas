"""
Celery app instance (Ch.15: Cloud Tasks & Workers).

**Broker choice, per this phase's brief**: "Celery + Redis broker (faster
to start with, since Redis already exists from Phase 3)." One nuance
worth being explicit about, since it's easy to get wrong: Phase 3's
`app/core/redis_client.py` talks to Upstash over its REST API — deliberate,
per that file's own docstring, because REST fits FastAPI's request/response
cycle with no connection pool to manage. Celery's Redis broker/backend
transport does NOT speak REST — it needs the plain Redis wire protocol
over a `redis://` or `rediss://` URL. Upstash exposes both on the SAME
instance (REST is a convenience layer on top of a real Redis server), so
this reuses the identical Upstash database Phase 3 already provisioned —
"Redis already exists from Phase 3" is still true — just over its other
protocol. No second Redis instance, no second bill, no second thing to
provision.

Env var required (new in this phase, see .env.example):
    CELERY_BROKER_URL   e.g. rediss://default:<password>@<host>:6379
                         (Upstash's dashboard shows this exact string
                         under "Connect" -> "Redis" tab — NOT the REST URL)

Retry model (Ch.15's fig 15.1: "fire-and-track, not fire-and-forget" +
"Cloud Tasks guarantees at-least-once delivery... retrying automatically
on a 5xx response, which is what makes the pipeline resilient to a
worker crashing mid-render"). Celery's closest equivalent to "retry
automatically if the worker crashed mid-job" is the combination of:

  - `task_acks_late = True` — the broker only marks a task as done AFTER
    it finishes (default Celery acks BEFORE running, which would mean a
    worker that dies mid-render just loses the job silently).
  - `task_reject_on_worker_lost = True` — if the worker process is killed
    (not just the task raising an exception) while a late-ack task is
    running, the unacked task is put back on the queue for another
    worker to pick up, instead of vanishing with the dead worker.

Together these two settings are what actually satisfies this phase's
Definition of Done ("manually crashing the render worker mid-job results
in an automatic retry, not a stuck job") — it's a broker-level guarantee,
not something each task has to implement itself. Individual tasks (see
voice_worker.py etc.) additionally use `autoretry_for` for their own
transient failures (a flaky TTS API call, a YouTube 5xx) — that's a
different, complementary case: the worker process is alive, the task
itself failed and should be retried with backoff.
"""

from __future__ import annotations

import os
import ssl

from celery import Celery

celery_app = Celery(
    "ai_carryon_workers",
    broker=os.environ["CELERY_BROKER_URL"],
    backend=os.environ["CELERY_BROKER_URL"],
    include=[
        "app.workers.voice_worker",
        "app.workers.thumbnail_worker",
        "app.workers.render_worker",
        "app.workers.upload_worker",
    ],
)

# Upstash's rediss:// endpoint needs an explicit ssl_cert_reqs setting --
# Celery refuses to guess a default for a security-sensitive option like
# this. CERT_NONE matches Upstash's managed cert setup (no custom CA to
# pin here); revisit if Upstash ever documents a stricter recommendation.
_redis_ssl_opts = {"ssl_cert_reqs": ssl.CERT_NONE}

celery_app.conf.update(
    broker_use_ssl=_redis_ssl_opts,
    redis_backend_use_ssl=_redis_ssl_opts,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # pairs with acks_late: don't hoard extra jobs on a worker that might die
    task_track_started=True,
    result_expires=60 * 60 * 24,  # 24h — long enough to debug a run, short enough not to bloat Redis forever
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)
