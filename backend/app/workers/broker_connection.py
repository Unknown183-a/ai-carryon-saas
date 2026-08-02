"""
Per-channel Celery broker connection cache (Ch.15 extension).

Deliberately NOT a second full Celery app: every task in this project is
registered once, at import time, on the single `app.workers.celery_app`
instance via `include=[...]` — building a second `Celery(...)` app would
mean none of those tasks exist on it unless every worker module were
imported and re-decorated a second time.

Celery's `Task.apply_async` / `chain.apply_async` accept a `connection`
kwarg (a kombu Connection) that, when given, is used instead of the
app's own pooled connection for THAT call only -- the task registry,
serializers, and retry config still come from the shared `celery_app`.
That's exactly what per-channel routing needs: same tasks, different
physical broker per enqueue call.
"""

from __future__ import annotations

from functools import lru_cache

from kombu import Connection

from app.workers.celery_app import _with_ssl_cert_reqs


@lru_cache(maxsize=None)
def get_broker_connection(broker_url: str) -> Connection:
    """Returns a cached kombu Connection for `broker_url`. Cached per
    URL so repeated runs for the same channel reuse one connection
    instead of opening a new one every enqueue call.
    """
    return Connection(_with_ssl_cert_reqs(broker_url))
