"""
Celery task wrapper around tenant_platform.infra.broker_provisioning.

Runs on the SHARED platform worker (the plain celery_app, not a
per-channel override) — this task provisions infrastructure using the
platform's own GCP credentials, unrelated to any single channel's own
isolated broker, so it belongs on the same queue as any other
platform-level housekeeping task.

Replaces the earlier FastAPI BackgroundTasks approach (see commits
aea44bf, 10e01b0) — running Cloud Run/Secret Manager API calls inline
in the gateway process risked starving unrelated requests (caused a
real ~5min gateway stall on 2026-08-02). Celery's own retry/at-least-
once machinery (task_acks_late, task_reject_on_worker_lost — already
configured on celery_app) is also a better fit than BackgroundTasks,
which has no retry story at all if the gateway process restarts
mid-task.
"""

from __future__ import annotations

from app.workers.celery_app import celery_app
from tenant_platform.infra.broker_provisioning import provision_channel_broker


@celery_app.task(
    name="workers.provision_channel_broker",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def provision_channel_broker_task(self, project_id: str, channel_id: str, broker_url: str) -> None:
    """Celery entry point. provision_channel_broker() already catches and
    logs its own exceptions rather than raising (so a failure doesn't
    leave a channel's provider-key save looking broken) — this task
    layer exists for queueing/retry semantics, not additional error
    handling on top of that.
    """
    provision_channel_broker(project_id, channel_id, broker_url)
