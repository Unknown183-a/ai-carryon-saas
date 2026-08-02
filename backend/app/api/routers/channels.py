"""
GET /channels, POST /channels, POST /channels/{channel_id}/generate.

Phase 6: POST /channels now runs through the Channel Factory (Ch.12d)
instead of a raw Firestore write, /generate loads a real database-driven
Channel Brain instead of Phase 4's one hardcoded channel, and every
channel-scoped route goes through the Ch.12e Permission Check
(`require_channel_access`) before touching anything else — a request for
a channel outside the caller's workspace is rejected there, never
reaching LangGraph or any other downstream service.

Phase 7: a passing review no longer ends the run silently — the graph's
new `enqueue_render` terminal node (Ch.15) hands off to the async worker
chain and the response now includes `render_task_id` /
`render_status` so the caller can tell "reviewed, and a video is being
rendered/uploaded in the background" apart from "reviewed" alone. Both
are `None` for a run whose `review_verdict` is `"fail"` — nothing was
enqueued, per graph.py's own routing.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from google.cloud.firestore import Client

from app.api.dependencies import get_current_user, get_firestore
from app.database.firestore_collections import (
    find_workspace_for_uid,
    get_provider_keys,
    get_schedule,
    list_channels_for_workspace,
    list_runs_for_channel,
    store_provider_keys,
)
from app.models.channel import ChannelCreateRequest, ProviderKeyStatus, ProviderKeys
from app.services.generation_service import run_generation
from tenant_platform.factory.factory import ChannelValidationError
from tenant_platform.factory.factory import create_channel as factory_create_channel
from tenant_platform.security.permissions import require_channel_access
from tenant_platform.infra.broker_provisioning import provision_channel_broker
from tenant_platform.security.provider_keys import encrypt_provider_keys

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("")
def list_channels(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_firestore),
):
    """Every channel belonging to the caller's own workspace — never
    another workspace's, even one the caller could otherwise guess the
    id of (Ch.12e).
    """
    workspace = find_workspace_for_uid(db, user["uid"])
    if workspace is None:
        return []
    return list_channels_for_workspace(db, workspace["workspace_id"])


@router.post("")
def create_channel(
    payload: ChannelCreateRequest,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_firestore),
):
    uid = user["uid"]
    workspace = find_workspace_for_uid(db, uid)
    if workspace is None:
        # Ch.12c: a Workspace is created via POST /workspaces on first
        # login. A user hitting POST /channels before that exists gets a
        # clear error instead of a channel silently orphaned from any
        # workspace (which would make it unreachable — nothing could ever
        # pass the Ch.12e permission check for it).
        raise HTTPException(
            status_code=400,
            detail="No workspace found for this user — call POST /workspaces first.",
        )
    try:
        return factory_create_channel(payload, workspace["workspace_id"], uid, db)
    except ChannelValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def _status_from_stored(stored: dict) -> ProviderKeyStatus:
    return ProviderKeyStatus(**{field: field in stored for field in ProviderKeyStatus.model_fields})


@router.get("/{channel_id}/provider-keys", response_model=ProviderKeyStatus)
def get_provider_key_status(
    channel_doc: dict = Depends(require_channel_access),
    db: Client = Depends(get_firestore),
):
    """Closes the Phase 11 gap: the Providers screen needs to know
    which keys are already set for a channel so it can show connection
    status. Goes through the same Ch.12e `require_channel_access` chain
    as every other channel-scoped route, then returns booleans only —
    never a decrypted value, per Ch.12d's rule that a stored provider
    key is never returned from an API response.
    """
    stored = get_provider_keys(db, channel_doc["channel_id"])
    return _status_from_stored(stored)


@router.patch("/{channel_id}/provider-keys", response_model=ProviderKeyStatus)
def update_provider_keys(
    payload: ProviderKeys,
    background_tasks: BackgroundTasks,
    channel_doc: dict = Depends(require_channel_access),
    db: Client = Depends(get_firestore),
):
    """Closes the other half of the Phase 11 gap: rotating or adding a
    provider key without recreating the whole channel. Only fields the
    caller actually supplies (non-None/non-empty) are touched —
    `encrypt_provider_keys` already drops empty values, and this merges
    the result into whatever's already stored rather than overwriting
    the whole doc, so an omitted field keeps its existing value.
    """
    channel_id = channel_doc["channel_id"]
    updates = encrypt_provider_keys(payload.model_dump())
    if updates:
        existing = get_provider_keys(db, channel_id)
        existing.update(updates)
        store_provider_keys(db, channel_id, existing)

    # NOTE: automatic provisioning (broker_provisioning.py) is
    # temporarily disabled here — running the ~1-5min Cloud Run deploy
    # operation inline via BackgroundTasks on 2026-08-02 caused the
    # gateway process to stall on unrelated requests (504s on /channels,
    # /workspaces) while it waited. The module itself is fine; it needs
    # to run somewhere that can't starve the request-handling process —
    # a real Celery task, or a separate Cloud Run Job — before being
    # re-wired here. See chat history for the incident.
    return _status_from_stored(get_provider_keys(db, channel_id))


@router.get("/{channel_id}/runs")
def list_channel_runs(
    channel_id: str,
    channel_doc: dict = Depends(require_channel_access),
    db: Client = Depends(get_firestore),
):
    """Closes the Phase 11 Logs gap: every finished (or errored) pipeline
    run for this channel, most recent first, including the step-by-step
    `run_log` LangGraph already accumulates per run
    (`ai.langgraph.state.PipelineState.run_log`) but which nothing
    persisted anywhere until now. Same `require_channel_access` gate as
    every other channel-scoped route — a run doc belongs to the channel
    that triggered it, same isolation guarantee as provider keys.
    """
    return list_runs_for_channel(db, channel_id)


@router.get("/{channel_id}/schedule")
def get_channel_schedule(
    channel_id: str,
    channel_doc: dict = Depends(require_channel_access),
    db: Client = Depends(get_firestore),
):
    """Closes the "when will this channel next auto-generate" gap: the
    dashboard has no visibility into the `schedules` doc
    `register_schedule` creates at channel-creation time (Ch.16, Phase
    8) — this is the read side of that, gated by the same
    `require_channel_access` chain as every other channel-scoped route.

    Returns None-valued fields (never a 404) for a channel that somehow
    has no schedule doc yet — that's a real, displayable state ("not
    scheduled"), not an error, and matches how the scheduler's own
    `is_due()` already treats a missing doc as "not due" rather than
    raising.
    """
    schedule = get_schedule(db, channel_id)
    if schedule is None:
        return {
            "channel_id": channel_id,
            "enabled": False,
            "upload_schedule": channel_doc.get("upload_schedule"),
            "last_run_at": None,
            "next_run_at": None,
        }
    return {
        "channel_id": channel_id,
        "enabled": schedule.get("enabled", True),
        "upload_schedule": schedule.get("upload_schedule"),
        "last_run_at": schedule.get("last_run_at"),
        "next_run_at": schedule.get("next_run_at"),
    }


@router.post("/{channel_id}/generate")
async def generate_video(
    channel_id: str,
    channel_doc: dict = Depends(require_channel_access),
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_firestore),
):
    """Runs the full Trend -> Research -> Planner -> Parallel(6) ->
    Review pipeline for one channel and returns the reviewed script +
    SEO + thumbnail brief — plus, on a passing review, the async render
    chain's task id (Ch.15, Phase 7): rendering and uploading continue
    in the background after this endpoint has already returned, so
    `render_task_id`/`render_status` describe work still in flight, not
    work already finished.

    `require_channel_access` has already run the full Ch.12e chain
    (resolved the channel, resolved its workspace, confirmed the caller's
    uid is a member) before this function body executes at all.

    Phase 8: the actual LangGraph invocation now lives in
    `app/services/generation_service.py`'s `run_generation`, shared with
    `POST /internal/scheduler/run-due-channels` (Ch.16) so a
    Scheduler-triggered run and a human-triggered run can never drift
    into different behavior.

    Fails fast with 400 if this channel hasn't connected its own YouTube
    account yet (unless it's the operator's own HARDCODED_CHANNEL_ID
    dev/test channel) — otherwise the full Trend -> ... -> Render chain
    would run to completion only to have `upload_worker.py` reject it at
    the very last step (`YouTubeNotConnectedError`), wasting a render's
    worth of time/API cost on a run that could never have succeeded.
    """
    from ai.langgraph.hardcoded_channel import HARDCODED_CHANNEL_ID

    if channel_id != HARDCODED_CHANNEL_ID:
        encrypted = get_provider_keys(db, channel_id)
        if not encrypted.get("youtube_oauth_token"):
            raise HTTPException(
                status_code=400,
                detail=(
                    "This channel hasn't connected a YouTube account yet. "
                    "Go to Providers and click 'Connect with Google' for this "
                    "channel before generating a video."
                ),
            )

    return await run_generation(channel_id, channel_doc, user["uid"], db=db)
