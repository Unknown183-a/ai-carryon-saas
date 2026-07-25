"""
Scheduler service (Ch.16, Phase 8): the two things a `schedules` Firestore
document is for — getting created when a channel is (fig 12d.1's
"Register Scheduler" step, left unimplemented on purpose by Phase 6's
Channel Factory until this phase existed to fill it in — see
`tenant_platform/factory/factory.py`'s updated module docstring), and
getting queried by the Scheduler-triggered endpoint
(`app/api/routers/internal_scheduler.py`) to decide who's due right now.

Firestore access itself lives in `app/database/firestore_collections.py`
(this module never calls `db.collection(...)` directly) — same layering
every other phase already uses.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional

from app.database.firestore_collections import get_schedule, list_enabled_schedules, upsert_schedule
from tenant_platform.scheduler.schedule_rules import compute_next_run_at, is_due


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def register_schedule(
    db,
    channel_id: str,
    upload_schedule: str,
    now: Optional[datetime.datetime] = None,
) -> dict[str, Any]:
    """Factory Step (fig 12d.1) "Register Scheduler": called once, at
    channel-creation time, from `tenant_platform/factory/factory.py`.
    Creates the channel's `schedules` doc, enabled by default, with its
    first `next_run_at` already computed — a freshly created channel
    doesn't have to wait for someone to separately "turn scheduling on."
    """
    now = now or _now()
    next_run_at = compute_next_run_at(upload_schedule, after=now)
    data = {
        "channel_id": channel_id,
        "upload_schedule": upload_schedule,
        "enabled": True,
        "last_run_at": None,
        "next_run_at": next_run_at.isoformat(),
        "created_at": now.isoformat(),
    }
    return upsert_schedule(db, channel_id, data)


def list_due_channel_ids(db, now: Optional[datetime.datetime] = None) -> list[str]:
    """Every channel_id whose schedule is enabled AND due as of `now`.
    See `firestore_collections.list_enabled_schedules`'s docstring for
    why the `next_run_at <= now` half of this check happens here, in
    Python, rather than as a second Firestore query clause.
    """
    now = now or _now()
    return [
        schedule["channel_id"]
        for schedule in list_enabled_schedules(db)
        if is_due(schedule, now)
    ]


def mark_schedule_ran(
    db,
    channel_id: str,
    ran_at: datetime.datetime,
    upload_schedule: Optional[str] = None,
) -> None:
    """Called once per due channel, after `internal_scheduler.py` has
    finished attempting that channel's run — success, failure, or
    skipped alike (see that router's own comment on why: a channel stuck
    in a bad state should sit out until its NEXT scheduled slot, not get
    retried on every single poll of this endpoint, which would look
    indistinguishable from a retry storm).

    `upload_schedule` is re-read from the channel's own schedule doc if
    not passed explicitly, so a schedule whose frequency changed after
    creation still advances correctly.
    """
    existing = get_schedule(db, channel_id) or {}
    schedule_kind = upload_schedule or existing.get("upload_schedule", "1_per_day")
    next_run_at = compute_next_run_at(schedule_kind, after=ran_at)
    upsert_schedule(
        db,
        channel_id,
        {
            "last_run_at": ran_at.isoformat(),
            "next_run_at": next_run_at.isoformat(),
        },
    )
