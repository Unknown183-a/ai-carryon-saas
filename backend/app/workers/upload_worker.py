"""
Upload Worker (Ch.15: "YouTube upload... Worker... Depends on file size &
API latency" — the other reason this can't run inline, alongside
render's 1-4 minutes: an external API's own latency is not something
this pipeline controls).

Last link in the render chain. Uses a channel's own stored YouTube OAuth
token if it submitted one at creation (Ch.12d's provider-key table),
decrypting it the same way any other per-channel provider key is
decrypted (`tenant_platform/security/provider_keys.py`) — never the
platform-default `YOUTUBE_TOKEN_B64` for a channel that supplied its
own, so one channel's videos are never uploaded to another channel's
YouTube account. Falls back to the platform default only when the
channel didn't supply one, per Ch.12d: "falls back to platform default."

`retry_kwargs={"max_retries": 5}` is higher here than the other three
workers' 2-3 — deliberately, matching Ch.15's own callout that upload
"depends on ... API latency": a transient YouTube quota hiccup or 5xx
is exactly the kind of failure this phase's Definition of Done is about
("Confirm retry-on-5xx behavior actually retries"), and it's the LAST
step — a render that succeeded shouldn't be thrown away over a
retryable upload failure that a few more attempts would likely clear.
"""

from __future__ import annotations

from typing import Any

from app.workers.celery_app import celery_app
from integrations.youtube.client import upload_video


def _channel_youtube_token(channel_id: str) -> str | None:
    """Best-effort lookup of a channel's own stored YouTube OAuth token,
    decrypted. Returns None (falls back to the platform default in
    integrations/youtube/client.py) if the channel never supplied one,
    Firestore isn't reachable, or the channel doesn't exist for any
    reason — an upload should still attempt the platform default rather
    than hard-fail on a lookup problem unrelated to the video itself.
    """
    try:
        from app.api.dependencies import get_firestore
        from app.database.firestore_collections import get_provider_keys
        from tenant_platform.security.provider_keys import decrypt_provider_keys

        db = get_firestore()
        encrypted = get_provider_keys(db, channel_id)
        if not encrypted.get("youtube_oauth_token"):
            return None
        return decrypt_provider_keys(encrypted)["youtube_oauth_token"]
    except Exception:  # noqa: BLE001 — see module docstring: fall back, don't hard-fail
        return None


@celery_app.task(
    name="workers.upload_to_youtube",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_kwargs={"max_retries": 5},
)
def upload_to_youtube(payload: dict[str, Any]) -> dict[str, Any]:
    channel_id = payload["channel_id"]
    video_path = payload["video_path"]
    seo = payload.get("seo") or {}
    description = payload.get("description", "")
    tags = payload.get("tags") or []

    title = seo.get("title") or payload.get("channel_config", {}).get("name", "AI CarryON")
    token_json = _channel_youtube_token(channel_id)

    youtube_video_id = upload_video(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        token_json=token_json,
    )

    return {**payload, "youtube_video_id": youtube_video_id, "status": "uploaded"}
