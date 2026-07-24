"""
The one hardcoded channel Phase 4 runs against.

Per this phase's brief: "Hardcode one channel's config in code (no
database-driven config yet)." This dict is that config. In Phase 6, the
same shape moves into Firestore via the Channel Factory (Ch.12d) and
becomes one of N channels a real user created through the onboarding
form — nothing here is meant to survive as-is past that phase.

Modeled on the real "AI carryON" YouTube channel (@AIcarryONAI) — an
AI/coding/future-tech Shorts channel — per this phase's planning
conversation, so `POST /channels/ai_carryon/generate` produces output
that's actually plausible for that channel, not a placeholder.
"""

from __future__ import annotations

HARDCODED_CHANNEL_ID = "ai_carryon"

HARDCODED_CHANNEL: dict = {
    "channel_id": HARDCODED_CHANNEL_ID,
    "name": "AI carryON",
    "youtube_handle": "@AIcarryONAI",
    "country": "IN",
    "language": "en",
    "category": "AI, coding, and future technology",
    "brand": {
        "tagline": "AI, coding, and future technology.",
        "tone": "energetic, curious, slightly futuristic",
        "logo_position": "bottom_right",
    },
    "format": "shorts",  # this channel's existing 176 videos are Shorts
    "target_audience": "18-35 developers and AI-curious tech enthusiasts",
    "upload_schedule": "1_per_day",  # Ch.12d field; not enforced yet — Scheduler is Phase 8
    "preferred_model": "gemini/gemini-1.5-flash",
    "voice_profile": "confident_tech_explainer_male",
    "thumbnail_style": "bold_text_high_contrast",
}
