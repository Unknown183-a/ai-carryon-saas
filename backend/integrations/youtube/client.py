"""
YouTube Data API v3 upload client.

**"the base64-encoded OAuth credential pattern already proven in the old
Railway deployment"** (this phase's PHASE.md) — Railway's filesystem is
ephemeral and has no secret-file mounting, so the old pipeline base64-
encoded the OAuth client-secrets JSON and the refreshed-token JSON into
two env vars (`YOUTUBE_CLIENT_SECRETS_B64`, `YOUTUBE_TOKEN_B64` — already
in `.env.example` since before this phase) and decoded them in-process
at call time instead of expecting real files on disk. Ported unchanged
here for the same reason: this project's deploy target (Ch.17, Phase 9)
isn't finalized yet, and this pattern already works regardless of which
one gets picked.

This is a per-CHANNEL credential in Ch.12d's provider-key table
(`youtube_oauth_token`), not a platform-wide one — a real multi-tenant
run should decrypt and pass a channel's own token (see
`tenant_platform/security/provider_keys.py`) rather than always reading
the platform-default env vars. `upload_video()` accepts an optional
`token_json` override for exactly that; falling back to
`YOUTUBE_TOKEN_B64` only when a channel hasn't supplied its own (Ch.12d:
"falls back to platform default"). Wiring that decrypt-and-pass-through
from a channel's stored key is `upload_worker.py`'s job, not this
module's — this module just knows how to talk to the API once it has a
token.

No refresh-token-exchange flow lives here (that's a one-time setup step
a human runs locally with `google-auth-oauthlib`'s installed-app flow,
per the SAD/old pipeline's README) — this only ever uses an
already-valid (or auto-refreshing, since `Credentials` objects refresh
themselves given a refresh_token) token, matching what a background
worker actually needs.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any

from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def _load_credentials(token_json: str | None = None) -> Credentials:
    """Builds a `Credentials` object from a base64-encoded token JSON —
    either the one passed in (a channel's own stored key, decrypted by
    the caller) or, if none given, the platform-default
    `YOUTUBE_TOKEN_B64` env var.
    """
    raw_b64 = token_json or os.environ.get("YOUTUBE_TOKEN_B64")
    if not raw_b64:
        raise RuntimeError(
            "No YouTube OAuth token available: neither a channel-specific "
            "token nor YOUTUBE_TOKEN_B64 is set."
        )

    info = json.loads(base64.b64decode(raw_b64))
    credentials = Credentials(
        token=info.get("token"),
        refresh_token=info.get("refresh_token"),
        token_uri=info.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=info.get("client_id"),
        client_secret=info.get("client_secret"),
        scopes=info.get("scopes", ["https://www.googleapis.com/auth/youtube.upload"]),
    )
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(GoogleAuthRequest())
    return credentials


def upload_video(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
    category_id: str = "28",  # "Science & Technology" — matches the old pipeline's default for the AI/coding channel
    privacy_status: str = "public",
    token_json: str | None = None,
) -> str:
    """Uploads `video_path` to YouTube and returns the resulting video id.

    Uses a resumable upload (`MediaFileUpload(..., resumable=True)`) —
    matters for the same reason rendering runs as a background job at
    all: a multi-minute upload over a flaky connection shouldn't have to
    restart from byte zero on a transient network blip. Raises on
    failure; retry is the caller's job (the Celery task's
    `autoretry_for`), per this module's own file-level convention.
    """
    credentials = _load_credentials(token_json)
    youtube = build("youtube", "v3", credentials=credentials)

    body: dict[str, Any] = {
        "snippet": {
            "title": title[:100],  # YouTube's own title length cap
            "description": description,
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {"privacyStatus": privacy_status},
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        _status, response = request.next_chunk()

    return response["id"]
