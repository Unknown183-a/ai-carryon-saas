"""
GET /workspaces/{workspace_id}/notifications and
POST /notifications/{notification_id}/read (Ch.19, Phase 10) — the
dashboard-facing half of an escalation (see
`tenant_platform/monitoring/alert_agent.py`'s module docstring for how a
notification doc gets created in the first place).

Membership check mirrors `tenant_platform/security/permissions.py`'s
`require_channel_access` shape, just against a workspace_id path param
instead of a channel_id one — there's no channel in scope here to
resolve a workspace_id FROM, unlike that dependency, so this stays a
small inline check rather than a shared dependency for what's currently
a single call site.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from google.cloud.firestore import Client

from app.api.dependencies import get_current_user, get_firestore
from app.database.firestore_collections import get_workspace, list_notifications, mark_notification_read

router = APIRouter(tags=["notifications"])


def _require_workspace_member(workspace_id: str, user: dict, db: Client) -> None:
    workspace = get_workspace(db, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail=f"Unknown workspace '{workspace_id}'")
    if user["uid"] not in workspace.get("members", []):
        raise HTTPException(status_code=403, detail="You do not have access to this workspace")


@router.get("/workspaces/{workspace_id}/notifications")
def get_notifications(
    workspace_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_firestore),
) -> dict[str, Any]:
    _require_workspace_member(workspace_id, user, db)
    return {"notifications": list_notifications(db, workspace_id)}


@router.post("/notifications/{notification_id}/read")
def mark_read(
    notification_id: str,
    user: dict = Depends(get_current_user),  # not otherwise used — presence alone is enough here
    db: Client = Depends(get_firestore),
) -> dict[str, str]:
    # No ownership check on notification_id itself (would need an extra
    # Firestore read to look up its workspace_id first, just to check
    # membership, for an action that only ever flips one boolean and
    # leaks nothing back to the caller either way) — matches this
    # project's existing bar for "cheap action, not worth a second
    # round-trip", same reasoning `mark_schedule_ran`'s docstring gives
    # for a different endpoint.
    mark_notification_read(db, notification_id)
    return {"status": "ok"}
