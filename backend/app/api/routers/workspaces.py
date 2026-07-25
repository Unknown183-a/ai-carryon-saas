"""
POST /workspaces (Ch.12c): creates a Workspace document on first login.

Ch.12c describes this as automatic the moment Firebase email
verification succeeds — that's a client-side/Cloud-Function trigger this
project doesn't have built (no Cloud Functions deployment exists yet).
The pragmatic equivalent here: the frontend calls this endpoint once
right after a successful login, and it's idempotent — a user who
already has a workspace gets that same one back rather than a duplicate,
so calling it on every login is always safe.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from google.cloud.firestore import Client

from app.api.dependencies import get_current_user, get_firestore
from tenant_platform.workspace.onboarding import get_or_create_workspace

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("")
def create_or_get_workspace(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_firestore),
):
    return get_or_create_workspace(user["uid"], db)
