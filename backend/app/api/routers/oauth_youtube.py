"""
GET /channels/{channel_id}/connect-youtube, GET /oauth/youtube/callback.

Closes the gap docs/decisions/0003-youtube-oauth-self-serve.md describes:
until now, a channel's `provider_keys.youtube_oauth_token` (Ch.12d) could
only be set by an operator manually running `youtube_auth.py` locally and
pasting the result into `PATCH /channels/{id}/provider-keys`. These two
routes do the same OAuth exchange automatically, triggered by the
channel's own owner clicking "Connect YouTube" in the frontend — no
operator, no local script, no manual token copy.

/connect-youtube goes through the same `require_channel_access` chain
(Ch.12e) as every other channel-scoped route — which needs a Firebase
JWT in an `Authorization` header. A plain browser navigation (the
frontend just setting `window.location.href` to this URL, or a plain
`<a href>`) can't carry that header, so this route does NOT redirect
the browser itself. It returns `{"auth_url": "..."}` as JSON, meant to
be called via the frontend's normal authenticated `apiFetch` (header
attached the usual way); the frontend then does the actual top-level
navigation to `auth_url` itself, once it already has it. Google's
consent screen sending the browser back to /oauth/youtube/callback is
the leg that's a plain, unauthenticated redirect Google controls — that
one carries no JWT by construction, which is exactly why `state` (see
tenant_platform/security/provider_keys.sign_channel_state) exists: it's
what proves that callback corresponds to a request that already passed
`require_channel_access`, without needing a header on a leg that can't
have one.
"""

from __future__ import annotations

import base64
import json
import os

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from google.cloud.firestore import Client
from google_auth_oauthlib.flow import Flow

from app.database.firestore_collections import get_provider_keys, store_provider_keys
from app.api.dependencies import get_firestore
from tenant_platform.security.permissions import require_channel_access
from tenant_platform.security.provider_keys import (
    encrypt_provider_keys,
    sign_channel_state,
    verify_channel_state,
)

router = APIRouter(tags=["oauth"])

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _redirect_uri() -> str:
    uri = os.environ.get("YOUTUBE_OAUTH_REDIRECT_URI")
    if not uri:
        raise HTTPException(
            status_code=503,
            detail="YOUTUBE_OAUTH_REDIRECT_URI is not configured",
        )
    return uri


def _build_flow() -> Flow:
    """Same client (YOUTUBE_CLIENT_SECRETS_B64) every channel's tokens are
    already issued against — see integrations/youtube/client.py's own
    module docstring for why this project stores OAuth material as
    base64 env vars rather than files on disk.
    """
    raw_b64 = os.environ.get("YOUTUBE_CLIENT_SECRETS_B64")
    if not raw_b64:
        raise HTTPException(status_code=503, detail="YOUTUBE_CLIENT_SECRETS_B64 is not configured")

    client_config = json.loads(base64.b64decode(raw_b64))
    return Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=_redirect_uri())


@router.get("/channels/{channel_id}/connect-youtube")
def connect_youtube(
    channel_doc: dict = Depends(require_channel_access),
) -> dict[str, str]:
    """Step 1: returns Google's consent-screen URL as JSON.
    `require_channel_access` has already confirmed the caller is a member
    of this channel's workspace before this handler runs at all — the
    same Ch.12e guarantee every other channel-scoped route gets. Called
    via the frontend's authenticated `apiFetch` (JWT header attached
    normally); the frontend does `window.location.href = auth_url`
    itself once it has this response — a raw redirect straight out of
    this endpoint would ask the *browser* to navigate here directly,
    which can't carry the Authorization header `require_channel_access`
    needs.
    """
    flow = _build_flow()
    auth_url, _unused_flow_state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",  # forces a refresh_token even on a re-connect
        state=sign_channel_state(channel_doc["channel_id"]),
    )
    return {"auth_url": auth_url}


@router.get("/oauth/youtube/callback")
def youtube_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Client = Depends(get_firestore),
):
    """Step 2: Google redirects here after the user grants (or denies)
    consent. No Firebase JWT is present on this leg — `state` (signed in
    step 1, decrypted+TTL-checked here) is what stands in for it.
    """
    frontend_url = os.environ.get("FRONTEND_URL", "").rstrip("/")

    if error:
        # User clicked "Cancel" on Google's consent screen — not a bug,
        # just an incomplete connect attempt. Lands back on /providers,
        # where "Connect" was clicked in the first place.
        return RedirectResponse(f"{frontend_url}/providers?youtube_error={error}")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    try:
        channel_id = verify_channel_state(state)
    except InvalidToken:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    flow = _build_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials

    # integrations/youtube/client.py's _load_credentials() always
    # base64-decodes whatever token it's given (that's the format
    # YOUTUBE_TOKEN_B64, the platform-default fallback, is stored in) —
    # so a per-channel token has to be stored the same way, or upload_video()
    # will throw the moment this channel's own token is actually used.
    token_b64 = base64.b64encode(creds.to_json().encode("utf-8")).decode("utf-8")
    updates = encrypt_provider_keys({"youtube_oauth_token": token_b64})
    existing = get_provider_keys(db, channel_id)
    existing.update(updates)
    store_provider_keys(db, channel_id, existing)

    return RedirectResponse(f"{frontend_url}/providers?youtube_connected=1&channel_id={channel_id}")
