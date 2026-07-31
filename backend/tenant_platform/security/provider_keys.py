"""
Provider-key encryption at rest (Ch.12d: "Every value in that table is
encrypted at rest and injected into a run only for the channel that owns
it").

Uses `cryptography`'s Fernet (symmetric, authenticated encryption) keyed
by a single platform-wide secret (`CHANNEL_SECRETS_ENCRYPTION_KEY`) —
not a per-channel key. This is the same tradeoff a lot of small
multi-tenant platforms make deliberately: rotating one platform-wide key
is a solved, occasional operation; managing N per-channel encryption
keys (their own storage, their own rotation, their own leak surface) is
a bigger system for a benefit this project doesn't need yet. What
matters for Ch.12d's isolation guarantee is which *channel* a key is
associated with in Firestore (each channel's row only ever decrypts to
that channel's own values) — not how many encryption keys exist.

Generate a real key for `.env` with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from __future__ import annotations

import os
from functools import lru_cache


@lru_cache(maxsize=1)
def _fernet():
    from cryptography.fernet import Fernet

    key = os.environ["CHANNEL_SECRETS_ENCRYPTION_KEY"]
    return Fernet(key.encode("utf-8") if isinstance(key, str) else key)


def encrypt_provider_keys(plain_keys: dict[str, str | None]) -> dict[str, str]:
    """Encrypts every non-empty value in `plain_keys`. Keys with a None
    or empty value are dropped entirely — an absent provider key (e.g.
    the user didn't supply their own OpenAI key, relying on the platform
    default per Ch.12d) should be absent from storage, not stored as an
    encrypted empty string.
    """
    fernet = _fernet()
    return {
        field: fernet.encrypt(value.encode("utf-8")).decode("utf-8")
        for field, value in plain_keys.items()
        if value
    }


def decrypt_provider_keys(encrypted_keys: dict[str, str]) -> dict[str, str]:
    """Decrypts every value in `encrypted_keys`. Used only at the point
    a pipeline run actually needs a channel's own provider credentials —
    never logged, never returned from an API response.
    """
    fernet = _fernet()
    return {field: fernet.decrypt(value.encode("utf-8")).decode("utf-8") for field, value in encrypted_keys.items()}


def decrypt_provider_keys_lenient(encrypted_keys: dict[str, str], *, channel_id: str) -> dict[str, str]:
    """Same job as `decrypt_provider_keys`, but one field that fails to
    decrypt (stale value from a rotated CHANNEL_SECRETS_ENCRYPTION_KEY,
    corruption, anything) is logged and skipped instead of taking every
    other field down with it.

    `decrypt_provider_keys`'s dict comprehension decrypts every field in
    one expression — a single bad value raises out of the whole call,
    and generation_service.py's run_generation wraps that fetch in a
    broad `except Exception: pass` (needed so a provider-key problem
    degrades to platform defaults instead of failing the whole run).
    Combined, one stale field silently zeroed out *every* override for
    that channel — including ones with nothing wrong with them — with no
    error anywhere. This is what run_generation should call instead.
    """
    import logging

    logger = logging.getLogger(__name__)
    fernet = _fernet()
    result: dict[str, str] = {}
    for field, value in encrypted_keys.items():
        try:
            result[field] = fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except Exception:  # noqa: BLE001 — one bad field must not take the others down
            logger.warning(
                "Provider key %r for channel %s failed to decrypt — skipping just that "
                "field; likely stale (encrypted under an old CHANNEL_SECRETS_ENCRYPTION_KEY) "
                "or corrupted. Re-saving it from the Providers screen will fix it.",
                field,
                channel_id,
            )
    return result


# ── OAuth state signing (Ch.12d extension: self-serve YouTube connect) ────
# The /connect-youtube -> Google consent -> /oauth/youtube/callback round
# trip has no Firebase JWT on the callback leg (Google redirects the
# browser directly, unauthenticated as far as this app is concerned) — so
# `state` has to both identify which channel this is for AND prove the
# callback actually originated from a request that already passed
# `require_channel_access`. Reusing the same Fernet key already
# provisioned for provider keys avoids introducing a second secret for
# what is, functionally, the same "prove you're allowed to touch this
# channel_id" guarantee Ch.12e already makes elsewhere.

OAUTH_STATE_TTL_SECONDS = 600  # 10 minutes — a user completing a Google
# consent screen takes seconds, not minutes; short-lived on purpose so an
# old, possibly-logged URL can't be replayed later.


def sign_channel_state(channel_id: str) -> str:
    return _fernet().encrypt(channel_id.encode("utf-8")).decode("utf-8")


def verify_channel_state(state: str) -> str:
    """Returns the channel_id if `state` is a valid, non-expired token
    from `sign_channel_state`. Raises `cryptography.fernet.InvalidToken`
    (expired or tampered) — the caller (the callback route) turns that
    into a 400, same as any other bad-input case.
    """
    from cryptography.fernet import Fernet  # noqa: F401 — triggers the same import error early as _fernet()

    return _fernet().decrypt(state.encode("utf-8"), ttl=OAUTH_STATE_TTL_SECONDS).decode("utf-8")
