"""
Tenant isolation & permission checking (Ch.12e).

fig 12e.1's chain: Workspace ID -> Channel ID -> Authenticated User ID ->
Permission Check, run in that order before any handler touches
Firestore, Redis, or Qdrant on the caller's behalf.

In this codebase's terms, "Channel ID" and "Authenticated User ID" are
already resolved by the time a route handler runs — Channel ID from the
URL path parameter, Authenticated User ID from `get_current_user`'s
verified JWT. What this module adds is the other two links in the
chain: resolving the channel's owning Workspace ID, and running the
Permission Check that confirms the authenticated user is actually a
member of it. `require_channel_access` is a FastAPI dependency any
channel-scoped route can add — same shape as `get_current_user` — and
it runs BEFORE the route handler body, so a rejected request never
reaches LangGraph, Redis, or Qdrant at all: the check fails at the
dependency-injection stage, which is the outermost point in the request
lifecycle short of middleware itself.

The isolation guarantee, stated plainly (Ch.12e): a user can only access
channels that belong to their own workspace — not partially, not
through a shared cache key, not through a vector search that forgot to
filter by channel_id. This module is the FastAPI-layer half of that
guarantee; Redis's `ch:{channel_id}:*` prefixing (app/core/redis_client.py)
and Qdrant's mandatory channel_id filter (app/core/qdrant_client.py,
built in Phase 5) are the other two layers Ch.12e's table describes.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException
from google.cloud.firestore import Client

from app.api.dependencies import get_current_user, get_firestore
from app.database.firestore_collections import get_channel, get_workspace


async def require_channel_access(
    channel_id: str,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_firestore),
) -> dict:
    """FastAPI dependency for any route with a `channel_id` path
    parameter. Returns the channel's Firestore document (so the route
    handler doesn't need a second lookup) if access is allowed.

    404 (not 403) for a channel that doesn't exist at all — matches
    Phase 4's existing behavior for an unknown channel_id and avoids
    leaking "this channel exists but isn't yours" information. 403 only
    once the channel is confirmed to exist and the caller's uid is
    confirmed absent from its workspace's member list.
    """
    channel = get_channel(db, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail=f"Unknown channel '{channel_id}'")

    workspace_id = channel.get("workspace_id")
    workspace = get_workspace(db, workspace_id) if workspace_id else None
    if workspace is None or user["uid"] not in workspace.get("members", []):
        raise HTTPException(status_code=403, detail="You do not have access to this channel")

    return channel
