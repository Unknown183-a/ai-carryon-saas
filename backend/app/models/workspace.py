"""
Workspace schema (Ch.12c): the container created for a user on first
login, before any Channel Brain exists. See `app/database/firestore_collections.py`
for the Firestore read/write side — this module is just the shape.
"""

from __future__ import annotations

from pydantic import BaseModel


class Workspace(BaseModel):
    workspace_id: str
    owner_uid: str
    members: list[str]  # uids with access to every channel this workspace owns (Ch.12e)
    created_at: str  # ISO 8601
