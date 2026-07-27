"""
ElevenLabs text-to-speech client — thin httpx wrapper, same pattern as
`integrations/gemini/client.py` and `integrations/groq/client.py`: one
function, raw bytes/text in, normalized output out, no SDK.

Env var required: ELEVENLABS_API_KEY

`voice_profile` (e.g. "confident_tech_explainer_male", from a channel's
DNA — see hardcoded_channel.py / Channel Brain) is resolved to a real
ElevenLabs voice_id through VOICE_PROFILE_MAP below rather than being
passed straight through, since "confident_tech_explainer_male" isn't
itself a valid ElevenLabs voice_id. New channels wanting a voice not yet
mapped fall back to DEFAULT_VOICE_ID rather than erroring the whole
run — a missing voice mapping shouldn't block a pipeline that otherwise
succeeded.
"""

from __future__ import annotations

import os

import httpx

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

# A handful of ElevenLabs' own stock voice_ids, picked to roughly match
# the tone each name implies. Extend this as channels with new
# voice_profile values get created (Ch.12d's Create-Channel form).
VOICE_PROFILE_MAP: dict[str, str] = {
    "confident_tech_explainer_male": "onwK4e9ZLuTAKqWW03F9",  # "Daniel"
    "confident_tech_explainer_female": "21m00Tcm4TlvDq8ikWAM",  # "Rachel"
    "warm_narrator_male": "pNInz6obpgDQGcFmaJgB",  # "Adam"
    "warm_narrator_female": "EXAVITQu4vr4xnSDxMaL",  # "Bella"
}
DEFAULT_VOICE_ID = VOICE_PROFILE_MAP["confident_tech_explainer_male"]


def resolve_voice_id(voice_profile: str | None) -> str:
    if not voice_profile:
        return DEFAULT_VOICE_ID
    return VOICE_PROFILE_MAP.get(voice_profile, DEFAULT_VOICE_ID)


def _elevenlabs_key(channel_id: str | None) -> str:
    """Per-channel ElevenLabs key from Firestore (Ch.12d provider-keys
    pattern, same as clips_worker.py's Pexels lookup), falling back to
    the platform-wide ELEVENLABS_API_KEY env var so channels that
    haven't been given their own key yet keep working off the shared
    default.
    """
    if channel_id:
        try:
            from app.api.dependencies import get_firestore
            from app.database.firestore_collections import get_provider_keys
            from tenant_platform.security.provider_keys import decrypt_provider_keys

            db = get_firestore()
            encrypted = get_provider_keys(db, channel_id)
            if encrypted.get("elevenlabs_api_key"):
                return decrypt_provider_keys(encrypted)["elevenlabs_api_key"]
        except Exception as e:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).error(
                f"ElevenLabs channel key lookup/decrypt failed for channel_id={channel_id!r}: {e!r}"
            )

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError(
            f"No ElevenLabs API key available for channel_id={channel_id!r}: "
            "neither a channel-specific key nor ELEVENLABS_API_KEY is set."
        )
    return api_key


def generate_speech(
    text: str, voice_profile: str | None, channel_id: str | None = None, timeout: float = 60.0
) -> bytes:
    """Returns raw MP3 bytes for `text` spoken in the resolved voice.
    Raises on any transport/HTTP error — retry is the caller's job (the
    Celery task's `autoretry_for`, per celery_app.py's module docstring),
    same division of responsibility as web_search.py's "one attempt,
    raise on failure" convention.
    """
    api_key = _elevenlabs_key(channel_id)

    voice_id = resolve_voice_id(voice_profile)
    response = httpx.post(
        ELEVENLABS_TTS_URL.format(voice_id=voice_id),
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.content
