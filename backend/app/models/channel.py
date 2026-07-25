"""
Channel schemas (Ch.12d's Create-Channel Form + provider-key table).

`ChannelCreateRequest` is the form itself — identity fields plus,
separately, the credentials that let the pipeline act on the user's
behalf. Every field in `ProviderKeys` is optional: per Ch.12d's table,
`gemini_api_key` "falls back to platform default" if the user doesn't
supply their own, and the rest simply aren't wired into a running pipeline
until the phase that uses them exists (YouTube upload is Phase 8, voice
generation is Phase 7, etc.) — Phase 6's job is to store them safely,
encrypted, per channel, not to consume all of them yet.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChannelBrand(BaseModel):
    tagline: str = ""
    tone: str = ""
    logo_position: str = "bottom_right"


class ProviderKeys(BaseModel):
    """Ch.12d's provider-key table. Every field optional and, when
    present, encrypted at rest (tenant_platform/security/provider_keys.py)
    before it ever reaches Firestore.
    """

    youtube_oauth_token: str | None = None
    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    openai_api_key: str | None = None
    elevenlabs_api_key: str | None = None
    google_cloud_project: str | None = None
    firebase_storage_bucket: str | None = None


class ChannelCreateRequest(BaseModel):
    """The Create-Channel Form (Ch.12d). `workspace_id` is deliberately
    NOT a field here — it comes from resolving the authenticated caller's
    own workspace server-side (tenant_platform/security/permissions.py),
    never from client input, so a request body can't claim a channel for
    a workspace the caller doesn't belong to.
    """

    name: str
    youtube_handle: str | None = None
    country: str = "US"
    language: str = "en"
    category: str
    brand: ChannelBrand = Field(default_factory=ChannelBrand)
    format: str = "shorts"
    target_audience: str | None = None
    upload_schedule: str = "1_per_day"
    preferred_model: str | None = None  # None -> platform default, per Ch.12d
    voice_profile: str | None = None
    thumbnail_style: str | None = None
    provider_keys: ProviderKeys = Field(default_factory=ProviderKeys)
