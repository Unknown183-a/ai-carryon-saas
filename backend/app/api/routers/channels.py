"""
GET /channels and POST /channels — raw Firestore reads/writes.

No factory logic yet (that's Phase 6). Just proves: authenticated user in,
document out, respecting the ownership model from Phase 1's security rules.
"""

from fastapi import APIRouter, Depends
from google.cloud.firestore import Client
from pydantic import BaseModel

from app.api.dependencies import get_current_user, get_firestore

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
