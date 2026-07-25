Owned by: **Phase 7 — async-workers (OAuth + upload logic — done), Phase 8 — scheduler (quota-aware calls — not yet)**

`client.py` — resumable upload via the YouTube Data API v3, using the
base64-encoded OAuth credential pattern from the old Railway deployment
(`YOUTUBE_CLIENT_SECRETS_B64` / `YOUTUBE_TOKEN_B64`), with a per-channel
token override (Ch.12d) falling back to the platform default.

See `../../../phases/` for that phase's full brief.
