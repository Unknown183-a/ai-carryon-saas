"""
POST /internal/scheduler/run-due-channels (Ch.16, Phase 8).

Not a dashboard/browser-facing route — this is what Cloud Scheduler (or,
until Phase 9's deploy target is decided, a cron-triggered HTTP call —
PHASE.md's task list explicitly allows deferring the GCP piece: "Cloud
Scheduler job (or cron-triggered endpoint if deferring GCP)") hits on a
timer, unattended. Guarded by `require_system_token`
(`tenant_platform/security/permissions.py`) instead of
`get_current_user` — the Ch.12e Permission Check still runs on every
request through this route, it's just checking a system role token
instead of a Firebase user JWT, per this phase's own task list.

For each channel whose `schedules` doc says it's due right now, this
calls the exact same pipeline invocation
`POST /channels/{id}/generate` uses (`app/services/generation_service.py`'s
`run_generation`) — same LangGraph graph, same response shape, just
triggered by the Scheduler instead of a human. One channel's failure is
caught and reported, never raised — a single bad channel config
shouldn't stop every other due channel's 9 AM IST run from happening.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from fastapi import APIRouter, Depends
from google.cloud.firestore import Client

from app.api.dependencies import get_firestore
from app.database.firestore_collections import get_channel
from app.services.generation_service import run_generation
from tenant_platform.scheduler.scheduler_service import list_due_channel_ids, mark_schedule_ran
from tenant_platform.security.permissions import require_system_token

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/internal/scheduler",
    tags=["internal-scheduler"],
    dependencies=[Depends(require_system_token)],
)


@router.post("/run-due-channels")
async def run_due_channels(db: Client = Depends(get_firestore)) -> dict[str, Any]:
    now = datetime.datetime.now(datetime.timezone.utc)
    due_channel_ids = list_due_channel_ids(db, now)

    results: list[dict[str, Any]] = []
    for channel_id in due_channel_ids:
        channel_doc = get_channel(db, channel_id)

        if channel_doc is None:
            # Channel was deleted after its schedule doc was written —
            # there's no channel document left to advance next_run_at
            # on, so just report it and move on; nothing left to clean
            # up here without a Phase 8 "delete schedule with channel"
            # hook, which isn't in this phase's scope.
            results.append({"channel_id": channel_id, "status": "skipped", "reason": "channel no longer exists"})
            continue

        if channel_doc.get("status") != "ready":
            # A channel stuck in "configuring" (or any other non-ready
            # state) still needs its schedule advanced — otherwise it'd
            # show up as "due" again on every single poll of this
            # endpoint until someone fixes it, which looks identical to
            # a retry storm from the outside.
            results.append(
                {
                    "channel_id": channel_id,
                    "status": "skipped",
                    "reason": f"channel status is '{channel_doc.get('status')}', not 'ready'",
                }
            )
            mark_schedule_ran(db, channel_id, now, channel_doc.get("upload_schedule"))
            continue

        try:
            run_result = await run_generation(
                channel_id,
                channel_doc,
                triggered_by_uid=channel_doc.get("owner_uid", "system:scheduler"),
            )
            results.append(
                {
                    "channel_id": channel_id,
                    "status": "ran",
                    "run_id": run_result.get("run_id"),
                    "review_verdict": run_result.get("review_verdict"),
                    "render_task_id": run_result.get("render_task_id"),
                }
            )
        except Exception as exc:  # noqa: BLE001 — one channel's failure must not sink the whole batch
            logger.exception("Scheduled generation failed for channel %s", channel_id)
            results.append({"channel_id": channel_id, "status": "error", "error": str(exc)})
        finally:
            mark_schedule_ran(db, channel_id, now, channel_doc.get("upload_schedule"))

    return {
        "checked_at": now.isoformat(),
        "due_count": len(due_channel_ids),
        "results": results,
    }
