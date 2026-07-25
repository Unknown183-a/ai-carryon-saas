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

import uuid

from fastapi import APIRouter, Depends, HTTPException
from google.cloud.firestore import Client

from app.api.dependencies import get_current_user, get_firestore
from app.database.firestore_collections import find_workspace_for_uid, list_channels_for_workspace
from app.models.channel import ChannelCreateRequest
from ai.langgraph.graph import get_graph
from tenant_platform.channels.brain import load_channel_brain
from tenant_platform.factory.factory import ChannelValidationError
from tenant_platform.factory.factory import create_channel as factory_create_channel
from tenant_platform.security.permissions import require_channel_access

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


@router.post("/{channel_id}/generate")
async def generate_video(
    channel_id: str,
    channel_doc: dict = Depends(require_channel_access),
    user: dict = Depends(get_current_user),
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
    """
    brain = load_channel_brain(channel_doc)

    initial_state = {
        "channel_id": channel_id,
        "parent_uid": user["uid"],
        "run_id": str(uuid.uuid4()),
        "channel_config": brain.to_pipeline_config(),
    }

    graph = get_graph()
    final_state = await graph.ainvoke(initial_state)

    return {
        "run_id": final_state["run_id"],
        "status": final_state.get("status"),
        "topic": final_state.get("topic"),
        "script": final_state.get("script"),
        "seo": final_state.get("seo"),
        "thumbnail_brief": final_state.get("thumbnail_brief"),
        "hook": final_state.get("hook"),
        "tags": final_state.get("tags"),
        "description": final_state.get("description"),
        "review_verdict": final_state.get("review_verdict"),
        "review_findings": final_state.get("review_findings"),
        "failure_reason": final_state.get("failure_reason"),
        "render_task_id": final_state.get("render_task_id"),
        "render_status": final_state.get("render_status"),
    }
