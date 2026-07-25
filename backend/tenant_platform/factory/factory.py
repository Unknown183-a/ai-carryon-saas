"""
Channel Factory (Ch.12d, fig 12d.1): what "Save" actually does when a
user submits the Create-Channel form.

Validate Configuration -> Create Firestore Record -> Create Redis
Namespace -> Create Qdrant Namespace -> Generate Channel DNA -> Register
Scheduler -> Channel Ready. fig 12d.1 lists one more step, Register
Monitoring (Ch.18), still deliberately unimplemented here — that
subsystem doesn't exist yet (Phase 10), so there's nothing to register
with. `status` stays `"configuring"` rather than `"ready"` until every
step in *this* chain succeeds; a future phase's Monitoring registration
can round the rest of the way out once it exists, without anything here
needing to change.

Phase 8 update: Register Scheduler is no longer a stub. Every channel
this factory creates gets a `schedules` Firestore doc
(`tenant_platform/scheduler/scheduler_service.register_schedule`) at
creation time, computed from the channel's own `upload_schedule` field —
a freshly created channel starts generating on its own schedule
immediately, not only once someone separately visits a settings screen
to "turn scheduling on."

What "Create Redis Namespace" and "Create Qdrant Namespace" actually do:
neither Redis nor Qdrant has a real "create a namespace" operation to
call — Ch.12b's namespacing is a *convention* (the `ch:{channel_id}:`
key prefix, the mandatory `channel_id` metadata filter), enforced by
every read/write going through `channel_key()` / `channel_filter()`
(app/core/redis_client.py, app/core/qdrant_client.py), not by a
provisioning step that reserves space up front. So these two steps are
real but lightweight: Redis gets one housekeeping marker key written
(proof the channel's namespace is "live" and inspectable, e.g. for a
future admin tool), and Qdrant gets `ensure_collections()` called
idempotently (usually a no-op, since it already ran at FastAPI startup —
Phase 5) rather than any collection actually being created per channel,
since the nine collections are shared and namespaced by metadata, not
duplicated per channel.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from app.core.redis_client import channel_key, get_redis
from app.database.firestore_collections import create_channel_record, update_channel_status
from app.models.channel import ChannelCreateRequest
from ai.rag.collections import ensure_collections
from tenant_platform.channels.brain import ChannelBrain
from tenant_platform.scheduler.scheduler_service import register_schedule
from tenant_platform.security.provider_keys import encrypt_provider_keys


class ChannelValidationError(ValueError):
    pass


def _validate(payload: ChannelCreateRequest) -> None:
    """Step 1: Validate Configuration. Pydantic already enforced field
    types/required-ness on the way in; this is the handful of business
    rules that aren't expressible as a type.
    """
    if not payload.name.strip():
        raise ChannelValidationError("Channel name cannot be empty")
    if not payload.category.strip():
        raise ChannelValidationError("Channel category cannot be empty")


def _generate_channel_id(name: str) -> str:
    """A short, human-legible id — a slug of the name plus a random
    suffix to avoid collisions between two channels named the same
    thing (in different workspaces, or even the same one).
    """
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "channel"
    return f"{slug}_{uuid.uuid4().hex[:8]}"


def create_channel(payload: ChannelCreateRequest, workspace_id: str, owner_uid: str, db) -> dict[str, Any]:
    """Runs the full fig 12d.1 chain and returns the finished channel
    document (DNA fields only — never provider keys, encrypted or not).
    """
    # Step 1: Validate Configuration
    _validate(payload)

    channel_id = _generate_channel_id(payload.name)

    # Step 2: Create Firestore Record (status="configuring" until every
    # later step succeeds)
    dna = {
        "workspace_id": workspace_id,
        "owner_uid": owner_uid,
        "status": "configuring",
        "name": payload.name,
        "youtube_handle": payload.youtube_handle,
        "country": payload.country,
        "language": payload.language,
        "category": payload.category,
        "brand": payload.brand.model_dump(),
        "format": payload.format,
        "target_audience": payload.target_audience,
        "upload_schedule": payload.upload_schedule,
        "preferred_model": payload.preferred_model or "gemini/gemini-1.5-flash",
        "voice_profile": payload.voice_profile,
        "thumbnail_style": payload.thumbnail_style,
    }
    create_channel_record(db, channel_id, dna)

    # Step 3: Create Redis Namespace — see module docstring for what this
    # means in practice. A marker key, not a provisioning call.
    redis = get_redis()
    redis.set(channel_key(channel_id, "_namespace_created_at"), dna_marker_timestamp())

    # Step 4: Create Qdrant Namespace — idempotent, usually a no-op by
    # this point (Phase 5 already ran it at startup). See module docstring.
    ensure_collections()

    # Provider keys, if the form included any — encrypted before storage,
    # stored separately from the main channel document (never returned
    # from this function or any GET /channels response).
    encrypted = encrypt_provider_keys(payload.provider_keys.model_dump())
    if encrypted:
        from app.database.firestore_collections import store_provider_keys

        store_provider_keys(db, channel_id, encrypted)

    # Step 5: Generate Channel DNA — the Firestore record IS the DNA
    # (Ch.12b: "Niche, region, language, tone, brand voice"); this just
    # confirms it round-trips through ChannelBrain cleanly before marking
    # the channel ready, so a malformed record fails loudly here instead
    # of surfacing later as a broken pipeline run.
    ChannelBrain(channel_id=channel_id, workspace_id=workspace_id, dna=dna).to_pipeline_config()

    # Step 6: Register Scheduler (Ch.16, Phase 8) — see module docstring.
    # Runs before the status flip below so a channel is never reported
    # "ready" while missing the schedule doc that lets it ever run
    # unattended.
    register_schedule(db, channel_id, payload.upload_schedule)

    # Step 7: Channel Ready
    update_channel_status(db, channel_id, "ready")
    dna["status"] = "ready"

    return {"channel_id": channel_id, **dna}


def dna_marker_timestamp() -> str:
    import datetime

    return datetime.datetime.now(datetime.timezone.utc).isoformat()
