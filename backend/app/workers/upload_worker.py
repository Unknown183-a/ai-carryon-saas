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

import logging
from typing import Any

from app.workers.celery_app import celery_app
from ai.langgraph.hardcoded_channel import HARDCODED_CHANNEL_ID
from integrations.youtube.client import upload_video

logger = logging.getLogger(__name__)


class YouTubeNotConnectedError(RuntimeError):
    """Raised when a real (non-platform-owner) channel has no YouTube
    OAuth token stored yet.

    Previously this case silently fell back to YOUTUBE_TOKEN_B64 — the
    platform operator's own token — which meant a user's video could
    end up uploaded to the *operator's* YouTube account with no error
    anywhere. That fallback is now reserved for HARDCODED_CHANNEL_ID
    only (the operator's own dev/test channel, per ai/langgraph/
    hardcoded_channel.py); every real user channel must have its own
    stored token or the upload refuses to run at all.
    """


def _channel_youtube_token(channel_id: str) -> str | None:
    """Looks up a channel's own stored YouTube OAuth token, decrypted.

    Only HARDCODED_CHANNEL_ID (the operator's own dev/test channel) is
    allowed to fall back to the platform-default YOUTUBE_TOKEN_B64 when
    it has no token of its own. Every other channel — i.e. every real
    user — must have connected its own YouTube account via
    oauth_youtube.py's self-serve flow; if it hasn't,
    YouTubeNotConnectedError is raised so the upload is refused loudly
    instead of silently landing on someone else's channel.
    """
    try:
        from app.api.dependencies import get_firestore
        from app.database.firestore_collections import get_provider_keys
        from tenant_platform.security.provider_keys import decrypt_provider_keys

        db = get_firestore()
        encrypted = get_provider_keys(db, channel_id)
        if not encrypted.get("youtube_oauth_token"):
            if channel_id == HARDCODED_CHANNEL_ID:
                logger.warning(
                    "No youtube_oauth_token stored for the operator's own "
                    "channel_id=%s — uploading with the platform-default "
                    "YOUTUBE_TOKEN_B64 instead (expected for this channel only).",
                    channel_id,
                )
                return None
            raise YouTubeNotConnectedError(
                f"channel_id={channel_id} has not connected a YouTube account "
                "yet. Ask the channel owner to click 'Connect with Google' on "
                "the Providers page before generating a video for this channel."
            )
        return decrypt_provider_keys(encrypted)["youtube_oauth_token"]
    except YouTubeNotConnectedError:
        raise
    except Exception as exc:  # noqa: BLE001 — Firestore/decrypt-layer failure, not "not connected"
        if channel_id == HARDCODED_CHANNEL_ID:
            logger.warning(
                "Per-channel YouTube token lookup failed for the operator's own "
                "channel_id=%s (%s: %s) — uploading with the platform-default "
                "YOUTUBE_TOKEN_B64 instead.",
                channel_id, type(exc).__name__, exc,
            )
            return None
        raise YouTubeNotConnectedError(
            f"Could not look up channel_id={channel_id}'s YouTube token "
            f"({type(exc).__name__}: {exc}). Refusing to fall back to the "
            "platform-default account for a real user channel."
        ) from exc


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
