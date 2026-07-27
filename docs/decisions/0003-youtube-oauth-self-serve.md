# 0003 — YouTube OAuth: from manual per-channel token to self-serve

## Status
Proposed (not yet implemented) — 2026-07-27

## Context
Today, connecting a channel's YouTube account requires a human (the platform
operator) to:
1. Run `backend/youtube_auth.py` locally, which opens a `localhost` OAuth
   redirect and prints tokens to a terminal.
2. Manually base64-encode the resulting token and push it to Secret Manager
   as a single shared `YOUTUBE_TOKEN_B64` value used by *every* channel.
3. Repeat step 1 every 7 days, because the OAuth client
   (`515114505847-6bi7gl2ilt4uddm0jdtujvejg78v6hl3.apps.googleusercontent.com`,
   GCP project `515114505847`) has Publishing status **Testing**, which caps
   refresh-token lifetime at 7 days and restricts login to a manually
   maintained Test Users allowlist (max 100 accounts).

This does not scale to "a user signs up and connects their own channel" —
it only works because the operator personally owns and re-authenticates
every channel currently in use (`@AIcarryONAI`, `@AIcarryONHindi`).

The data model and encryption layer for a real solution already exist:
- `backend/app/models/channel.py` — `ProviderKeys.youtube_oauth_token`
- `backend/tenant_platform/security/provider_keys.py` — Fernet
  encrypt/decrypt keyed by `CHANNEL_SECRETS_ENCRYPTION_KEY`, per Ch.12d

What's missing is the actual web-based OAuth exchange and the worker
reading per-channel tokens instead of one shared secret.

## Decision
Build a self-serve OAuth flow with four pieces:

1. **`GET /channels/{channel_id}/connect-youtube`** — builds the Google
   consent URL (same OAuth client as today) and redirects the user's
   browser to it, passing `channel_id` via the `state` param.
2. **`GET /oauth/youtube/callback`** — deployed on the real Cloud Run
   backend (not `localhost`). Exchanges the `code` for tokens server-side,
   encrypts `creds.to_json()` via `encrypt_provider_keys`, and writes it to
   that channel's Firestore doc under `provider_keys.youtube_oauth_token`.
3. **Worker change** — `upload_worker.py` / `integrations/youtube/client.py`
   stop reading the shared `YOUTUBE_TOKEN_B64` env var and instead look up
   and decrypt the specific channel's own token from Firestore.
4. **Google verification** — submit the OAuth consent screen for
   verification (Branding: homepage, privacy policy, ToS links; then
   Verification Center → Prepare for verification, including a demo video
   of the upload flow). This is required regardless of the code changes —
   Testing-mode login is blocked for any account not on the manual test
   user list, no matter how automated the surrounding flow is.

## Consequences
- New Authorized redirect URI must be added to the OAuth client's config:
  `https://ai-carryon-worker-590045983169.asia-south1.run.app/oauth/youtube/callback`
- Verification review typically takes 1–3 weeks; the manual 7-day
  re-auth workflow stays in place as a fallback until it's approved.
- Once live, each channel authenticates with its own YouTube account,
  removing the current single-shared-token bottleneck entirely.

## Handoff notes
Data model + encryption already built (Phase 6). Remaining work is the two
FastAPI routes, the worker's token-lookup change, and the Google
verification submission (Branding page fields + demo video). See chat log
2026-07-27 for the debugging session that surfaced this (fixed a separate
`tags_agent.py` bug and the Testing-mode 7-day token expiry along the way).
