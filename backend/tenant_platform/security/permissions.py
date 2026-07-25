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

import hmac
import os

from fastapi import Depends, HTTPException, Request
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


# ── System role token (Ch.16, Phase 8) ──────────────────────────────────
# PHASE.md's task list: "Confirm Scheduler-triggered requests pass
# through the Permission Check (Ch.12e) using a system role token, not a
# user JWT." There is deliberately no Firebase user behind a scheduled
# run — Cloud Scheduler (or, until Phase 9 picks a deploy target, a
# cron-triggered HTTP call, per this phase's own PHASE.md) has no uid to
# verify a JWT for, and shouldn't need one. What still has to hold: an
# unauthenticated caller must not be able to trigger every channel's
# pipeline on demand just by finding the route. `require_system_token`
# is that check's Scheduler-side equivalent of `get_current_user` — a
# FastAPI dependency, run at the same dependency-injection stage, just
# checking a shared secret instead of a signed JWT.

SYSTEM_TOKEN_HEADER = "X-Internal-Scheduler-Token"


def require_system_token(request: Request) -> None:
    """FastAPI dependency for `/internal/*` routes only (never for a
    channel-scoped, user-facing route — those keep using
    `require_channel_access` above). Raises 503 if the deployment never
    configured `INTERNAL_SCHEDULER_TOKEN` at all (fails closed — an
    unset secret must never be treated as "no token required"), 401 if
    the header is missing, 403 if it's present but wrong.

    `hmac.compare_digest` instead of `==` for the same reason
    `tenant_platform/security/provider_keys.py`'s encryption exists at
    all: a naive string comparison on a secret is a timing side-channel,
    however small — worth avoiding for free.
    """
    expected = os.environ.get("INTERNAL_SCHEDULER_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail="INTERNAL_SCHEDULER_TOKEN is not configured")

    provided = request.headers.get(SYSTEM_TOKEN_HEADER)
    if not provided:
        raise HTTPException(status_code=401, detail=f"Missing {SYSTEM_TOKEN_HEADER} header")
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="Invalid system token")
