"""
Workspace onboarding (Ch.12c) — the logic behind `POST /workspaces`.

Split out from the router the same way Channel creation is (router stays
thin and HTTP-shaped; the actual behavior lives here) — even though
today it's genuinely small, so if Ch.12c's onboarding grows (welcome
email, default channel scaffolding, etc.) it has an obvious home that
isn't the router file.
"""

from __future__ import annotations

from typing import Any

from app.database.firestore_collections import create_workspace, find_workspace_for_uid


def get_or_create_workspace(uid: str, db) -> dict[str, Any]:
    """Idempotent: a uid that already has a workspace gets that one back
    rather than a duplicate — safe to call on every login.
    """
    existing = find_workspace_for_uid(db, uid)
    if existing is not None:
        return existing
    return create_workspace(db, uid)
