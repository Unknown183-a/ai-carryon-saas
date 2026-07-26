"""
POST /internal/health-check/run (Ch.18-19, Phase 10).

Same shape as `internal_scheduler.py`'s `/internal/scheduler/run-due-channels`
(Ch.16 mechanism, reused per this phase's task list): not a
dashboard/browser-facing route, guarded by `require_system_token` instead
of `get_current_user`, meant to be hit on a short fixed timer (a second
Cloud Scheduler job, e.g. every 5 minutes, separate from the per-channel
"due channels" job) — unattended, no human in the loop for the common
case of everything being healthy.

Deliberately its own job/timer rather than piggybacking on the existing
`run-due-channels` poll: that one only fires when a channel is actually
due (Ch.16's whole point — don't hit the pipeline for channels with
nothing to do), which could be hours between polls for a channel on a
weekly schedule. Phase 10's Definition of Done needs a Redis outage
detected "within the polling interval" regardless of what any channel's
upload schedule happens to be — the two timers have genuinely different
jobs and shouldn't be coupled just because the same Cloud Scheduler
mechanism can run both.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from google.cloud.firestore import Client

from app.api.dependencies import get_firestore
from tenant_platform.monitoring.alert_agent import handle_health_check_result
from tenant_platform.monitoring.health_agent import run_health_check
from tenant_platform.security.permissions import require_system_token

router = APIRouter(
    prefix="/internal/health-check",
    tags=["internal-health-check"],
    dependencies=[Depends(require_system_token)],
)


@router.post("/run")
async def run_health_check_endpoint(db: Client = Depends(get_firestore)) -> dict[str, Any]:
    health_result = await run_health_check(db)
    alert_actions = handle_health_check_result(db, health_result)
    return {**health_result, "alert_actions": alert_actions}
