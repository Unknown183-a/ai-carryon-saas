"""
Firestore data-access layer (Phase 1: Firestore client + collection
access; Phase 6: multi-tenant data access patterns).

A thin layer over `google.cloud.firestore.Client` for the handful of
read/write shapes the rest of the app needs — collection names live in
exactly one place, and every caller (routers, the Channel Factory, the
permission chain) goes through here instead of writing
`db.collection("channels")` by hand in five different files.

This module only ever takes a `db` client as a parameter (never imports
`get_firestore` itself) so it stays trivially testable against a fake
Firestore double that implements the same handful of methods
(`collection().document().set()/.get()`, `.where().stream()`) — see
tests/phase6_multi_tenancy_test.py's `FakeFirestore`.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional

WORKSPACES = "workspaces"
CHANNELS = "channels"
PROVIDER_KEYS = "channel_provider_keys"
SCHEDULES = "schedules"  # Phase 8 (Ch.16) — one doc per channel, keyed by channel_id


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ── Workspaces (Ch.12c) ─────────────────────────────────────────────────

def find_workspace_for_uid(db, uid: str) -> Optional[dict[str, Any]]:
    """Returns the first workspace this uid is a member of, or None."""
    docs = db.collection(WORKSPACES).where("members", "array_contains", uid).stream()
    for doc in docs:
        return {"workspace_id": doc.id, **doc.to_dict()}
    return None


def create_workspace(db, uid: str) -> dict[str, Any]:
    doc_ref = db.collection(WORKSPACES).document()
    data = {"owner_uid": uid, "members": [uid], "created_at": _now_iso()}
    doc_ref.set(data)
    return {"workspace_id": doc_ref.id, **data}


def get_workspace(db, workspace_id: str) -> Optional[dict[str, Any]]:
    snapshot = db.collection(WORKSPACES).document(workspace_id).get()
    if not snapshot.exists:
        return None
    return {"workspace_id": snapshot.id, **snapshot.to_dict()}


# ── Channels (Ch.12b/12d) ────────────────────────────────────────────────

def create_channel_record(db, channel_id: str, data: dict[str, Any]) -> dict[str, Any]:
    doc_ref = db.collection(CHANNELS).document(channel_id)
    doc_ref.set(data)
    return {"channel_id": channel_id, **data}


def get_channel(db, channel_id: str) -> Optional[dict[str, Any]]:
    snapshot = db.collection(CHANNELS).document(channel_id).get()
    if not snapshot.exists:
        return None
    return {"channel_id": snapshot.id, **snapshot.to_dict()}


def list_channels_for_workspace(db, workspace_id: str) -> list[dict[str, Any]]:
    docs = db.collection(CHANNELS).where("workspace_id", "==", workspace_id).stream()
    return [{"channel_id": doc.id, **doc.to_dict()} for doc in docs]


def update_channel_status(db, channel_id: str, status: str) -> None:
    db.collection(CHANNELS).document(channel_id).set({"status": status}, merge=True)


# ── Provider keys (Ch.12d) — always encrypted before reaching this layer ──

def store_provider_keys(db, channel_id: str, encrypted_keys: dict[str, str]) -> None:
    """`encrypted_keys` must already be encrypted (see
    tenant_platform/security/provider_keys.py) — this layer stores
    whatever it's handed without touching it.
    """
    db.collection(PROVIDER_KEYS).document(channel_id).set(encrypted_keys)


def get_provider_keys(db, channel_id: str) -> dict[str, str]:
    """Returns the raw (still-encrypted) stored keys for a channel, or an
    empty dict if none were ever set. Decrypting is the caller's job.
    """
    snapshot = db.collection(PROVIDER_KEYS).document(channel_id).get()
    if not snapshot.exists:
        return {}
    return snapshot.to_dict()


# ── Schedules (Ch.16) ────────────────────────────────────────────────────
# One doc per channel, doc id == channel_id (same 1:1-by-id convention as
# PROVIDER_KEYS above). `tenant_platform/scheduler/scheduler_service.py`
# is the only caller that should ever touch these — this layer is just
# storage, same rule as every other collection in this file.

def upsert_schedule(db, channel_id: str, data: dict[str, Any]) -> dict[str, Any]:
    db.collection(SCHEDULES).document(channel_id).set(data, merge=True)
    return {"channel_id": channel_id, **data}


def get_schedule(db, channel_id: str) -> Optional[dict[str, Any]]:
    snapshot = db.collection(SCHEDULES).document(channel_id).get()
    if not snapshot.exists:
        return None
    return {"channel_id": snapshot.id, **snapshot.to_dict()}


def list_enabled_schedules(db) -> list[dict[str, Any]]:
    """Every schedule doc with `enabled == True`. Deliberately does NOT
    filter by `next_run_at` in the Firestore query itself — this
    project's Firestore access layer keeps every query to a single
    equality/array-contains clause (see every other `.where()` call in
    this file), so the "is it actually due right now" comparison is done
    in Python by the caller (`scheduler_service.list_due_channel_ids`)
    against each doc's `next_run_at`, not here.
    """
    docs = db.collection(SCHEDULES).where("enabled", "==", True).stream()
    return [{"channel_id": doc.id, **doc.to_dict()} for doc in docs]
