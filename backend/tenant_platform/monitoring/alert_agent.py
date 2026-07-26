"""
Alert Agent (Ch.19, Phase 10) — implements the retry-then-escalate table:
a failure is tracked per (scope, failure_mode), and once its retry
budget is exhausted, escalation fires exactly once per incident (not
once per subsequent poll — see `_already_escalated` below) as an
Incident Report (Firestore), a dashboard Notification (Firestore), and
an email (Resend). Serious failure modes also pause the affected
channel's schedule so a broken channel doesn't keep failing on every
future scheduled run until a human looks at it.

`scope` is either a real `channel_id` (a render/upload/quota failure
from the generation pipeline — Ch.19's own starting list) or the literal
string `"platform"` (an infra-level failure from `health_agent.py` —
Redis down, Qdrant unreachable, etc., nothing to do with any one
channel). Both go through the exact same policy table and escalation
path; only the "pause this channel's schedule" action only makes sense
for the channel-scoped case, and is skipped for "platform".

Retry counters live in Redis, not Firestore — they're transient by
design (Ch.19 doesn't need a permanent record of "this failed twice and
then recovered on the third try", only of actual escalations, which DO
get a permanent Firestore record). `ch:{channel_id}:alert:*` keeps the
channel-scoped counters inside the same namespacing convention
`redis_client.py`'s module docstring describes; platform-scope counters
use the literal `ch:platform:alert:*` for the same reason
`create_incident_report`'s docstring gives for reusing `channel_id` as a
sentinel there — one consistent key shape beats a special case.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from app.core.redis_client import get_redis
from app.database.firestore_collections import (
    create_incident_report,
    create_notification,
    set_schedule_enabled,
    update_channel_status,
)
from integrations.resend.client import send_alert_email

# (max_retries, serious) — "serious" gates the schedule-pause action.
# Ch.19's starting list plus a catch-all for health_agent.py's checks.
RETRY_ESCALATION_TABLE: dict[str, tuple[int, bool]] = {
    "render_failure": (2, True),
    "upload_failure": (2, True),
    "youtube_quota": (0, True),  # a quota error won't resolve by retrying seconds later — escalate immediately
    "health_check": (1, False),  # one bad poll could be a network blip; two consecutive (this + 1 retry) escalates
}
DEFAULT_POLICY = (1, False)

RETRY_COUNTER_TTL_SECONDS = 60 * 60  # 1h — a failure streak older than this is a new incident, not a continuation
ESCALATION_FLAG_TTL_SECONDS = 60 * 60 * 24  # 1 day — don't re-escalate the same still-failing check every single poll

# In-process fallback dedup for the "Redis itself is unreachable" branch
# of record_failure below — deliberately NOT Redis-backed (that's the
# whole point: this only gets used when Redis already isn't reachable).
# Resets on process restart, which just means a fresh Cloud Run
# instance might send one duplicate alert after a redeploy during an
# ongoing outage — an acceptable trade next to the alternative (this
# module silently crashing instead of alerting on the one failure mode,
# Redis itself being down, that Phase 10's Definition of Done names
# explicitly).
_redis_down_escalated: set[tuple[str, str]] = set()


def _policy(failure_mode: str) -> tuple[int, bool]:
    if failure_mode in RETRY_ESCALATION_TABLE:
        return RETRY_ESCALATION_TABLE[failure_mode]
    if failure_mode.startswith("health:"):
        return RETRY_ESCALATION_TABLE["health_check"]
    return DEFAULT_POLICY


def _counter_key(scope: str, failure_mode: str) -> str:
    return f"ch:{scope}:alert:{failure_mode}:count"


def _escalated_flag_key(scope: str, failure_mode: str) -> str:
    return f"ch:{scope}:alert:{failure_mode}:escalated"


def _already_escalated(redis, scope: str, failure_mode: str) -> bool:
    return redis.get(_escalated_flag_key(scope, failure_mode)) == "1"


def record_success(scope: str, failure_mode: str) -> None:
    """Called by the caller once a previously-failing check/task
    succeeds again — clears both the retry counter and the escalation
    flag, so a genuinely recovered service can escalate again later if
    it fails again, rather than staying silenced by a stale flag.
    """
    redis = get_redis()
    try:
        redis.delete(_counter_key(scope, failure_mode))
        redis.delete(_escalated_flag_key(scope, failure_mode))
    except Exception:  # noqa: BLE001
        # Redis unreachable — nothing to clear anyway if Redis itself is
        # down; the in-process dedup set (_redis_down_escalated) that
        # record_failure's fallback path uses isn't cleared here since
        # this function can't know whether Redis staying down is the
        # reason THIS particular (scope, failure_mode) succeeded or
        # not — it's a rare enough edge case (this failure mode
        # recovering in the same window Redis itself is unreachable)
        # not to be worth the extra plumbing to handle precisely.
        pass


def record_failure(
    db: Any,
    scope: str,
    failure_mode: str,
    detail: str,
    workspace_id: Optional[str] = None,
) -> dict[str, Any]:
    """The main entry point. Increments the retry counter for this
    (scope, failure_mode); escalates if the retry budget is exhausted
    and this incident hasn't already been escalated. Returns a small
    status dict for the caller to log/return, never raises on its own
    account (an alert that fails to send must not take down the request
    that reported the original failure — this function's own escalation
    steps below are wrapped for exactly that reason).
    """
    redis = get_redis()
    max_retries, serious = _policy(failure_mode)

    try:
        count = redis.incr(_counter_key(scope, failure_mode))
        redis.expire(_counter_key(scope, failure_mode), RETRY_COUNTER_TTL_SECONDS)
    except Exception:  # noqa: BLE001 — Redis itself is unreachable, see below
        # Can't do retry counting or Redis-backed dedup without Redis —
        # and this failure might BE "Redis is down" (Phase 10's
        # Definition of Done names this exact scenario), so the
        # escalation path below must not depend on Redis being
        # reachable. Skip straight to escalating, deduped in-process
        # instead (see _redis_down_escalated's module-level comment for
        # the trade-off this accepts).
        dedup_key = (scope, failure_mode)
        if dedup_key in _redis_down_escalated:
            return {"scope": scope, "failure_mode": failure_mode, "action": "already_escalated", "attempt": "unknown (redis unreachable)"}
        try:
            _escalate(db, scope, failure_mode, detail, serious, workspace_id)
            _redis_down_escalated.add(dedup_key)
            return {"scope": scope, "failure_mode": failure_mode, "action": "escalated", "attempt": "unknown (redis unreachable)"}
        except Exception as exc:  # noqa: BLE001 — see function docstring
            return {
                "scope": scope,
                "failure_mode": failure_mode,
                "action": "escalation_failed",
                "attempt": "unknown (redis unreachable)",
                "error": f"{type(exc).__name__}: {exc}",
            }

    if count <= max_retries:
        return {"scope": scope, "failure_mode": failure_mode, "action": "retry", "attempt": count}

    if _already_escalated(redis, scope, failure_mode):
        return {"scope": scope, "failure_mode": failure_mode, "action": "already_escalated", "attempt": count}

    try:
        _escalate(db, scope, failure_mode, detail, serious, workspace_id)
        redis.set(_escalated_flag_key(scope, failure_mode), "1", ex=ESCALATION_FLAG_TTL_SECONDS)
        return {"scope": scope, "failure_mode": failure_mode, "action": "escalated", "attempt": count}
    except Exception as exc:  # noqa: BLE001 — see module/function docstring
        return {
            "scope": scope,
            "failure_mode": failure_mode,
            "action": "escalation_failed",
            "attempt": count,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _escalate(
    db: Any,
    scope: str,
    failure_mode: str,
    detail: str,
    serious: bool,
    workspace_id: Optional[str],
) -> None:
    is_platform = scope == "platform"
    subject = f"[AI CarryON] {'Platform' if is_platform else f'Channel {scope}'} alert: {failure_mode}"
    incident = create_incident_report(
        db,
        {
            "channel_id": scope,
            "workspace_id": workspace_id,
            "failure_mode": failure_mode,
            "detail": detail,
            "serious": serious,
        },
    )

    if workspace_id:
        create_notification(
            db,
            workspace_id,
            {
                "channel_id": scope,
                "incident_id": incident["incident_id"],
                "failure_mode": failure_mode,
                "detail": detail,
                "severity": "serious" if serious else "warning",
            },
        )

    to_address = os.environ.get("ALERT_EMAIL_TO")
    if to_address:
        html_body = (
            f"<p><strong>{subject}</strong></p>"
            f"<p>{detail}</p>"
            f"<p>Incident ID: {incident['incident_id']}</p>"
        )
        send_alert_email(to_address, subject, html_body)

    if serious and not is_platform:
        set_schedule_enabled(db, scope, False)
        update_channel_status(db, scope, "paused_incident")


def handle_health_check_result(db: Any, health_result: dict[str, Any]) -> list[dict[str, Any]]:
    """Bridges `health_agent.run_health_check`'s output into this
    module's retry-then-escalate policy — one `failure_mode` of
    `health:{service}` per failing service (`health:redis`,
    `health:qdrant`, etc.), always scope `"platform"` since none of
    these checks are about any one channel. A passing service calls
    `record_success` so a previously-failing-then-recovered check can
    escalate again if it fails again later, rather than staying silenced.
    """
    actions = []
    for service in health_result.get("services", []):
        failure_mode = f"health:{service['service']}"
        if service["ok"]:
            record_success("platform", failure_mode)
        else:
            actions.append(record_failure(db, "platform", failure_mode, service["detail"]))
    return actions
