"""
GET /channels and POST /channels — raw Firestore reads/writes.

No factory logic yet (that's Phase 6). Just proves: authenticated user in,
document out, respecting the ownership model from Phase 1's security rules.

Phase 4: POST /channels/{id}/generate — starts a full pipeline run for the
one hardcoded channel (Ch.03's "How FastAPI talks to LangGraph": build one
state dict, hand it to graph.ainvoke(), control belongs to the orchestrator
from there).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from google.cloud.firestore import Client
from pydantic import BaseModel

from app.api.dependencies import get_current_user, get_firestore
from ai.langgraph.graph import get_graph
from ai.langgraph.hardcoded_channel import HARDCODED_CHANNEL, HARDCODED_CHANNEL_ID

router = APIRouter(prefix="/channels", tags=["channels"])


class ChannelCreate(BaseModel):
    name: str


@router.get("")
def list_channels(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_firestore),
):
    uid = user["uid"]
    docs = db.collection("channels").where("uid", "==", uid).stream()
    return [{"id": doc.id, **doc.to_dict()} for doc in docs]


@router.post("")
def create_channel(
    payload: ChannelCreate,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_firestore),
):
    uid = user["uid"]
    doc_ref = db.collection("channels").document()
    doc_ref.set({"uid": uid, "name": payload.name})
    return {"id": doc_ref.id, "uid": uid, "name": payload.name}


@router.post("/{channel_id}/generate")
async def generate_video(
    channel_id: str,
    user: dict = Depends(get_current_user),
):
    """Runs the full Trend -> Research -> Planner -> Parallel(6) -> Review
    pipeline for one channel and returns the reviewed script + SEO +
    thumbnail brief.

    Phase 4 scope: `channel_id` must be the one hardcoded channel — no
    Firestore lookup yet (that's Phase 6, once channels are database-driven).
    """
    if channel_id != HARDCODED_CHANNEL_ID:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Unknown channel '{channel_id}'. Phase 4 only runs the "
                f"hardcoded channel '{HARDCODED_CHANNEL_ID}' — per-channel "
                f"lookup arrives in Phase 6."
            ),
        )

    initial_state = {
        "channel_id": channel_id,
        "parent_uid": user["uid"],
        "run_id": str(uuid.uuid4()),
        "channel_config": HARDCODED_CHANNEL,
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
    }
