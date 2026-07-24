"""
Thin Gemini API client — auth, request formatting, the actual HTTP call.

No "which model for which task" logic here (that's backend/ai/models/ —
the registry that decides *which* client to call). This file only knows
how to talk to Gemini once someone's already decided to.

Uses the current `google-genai` SDK. The older `google.generativeai`
package is fully deprecated (no updates or bug fixes) as of when this was
written — worth remembering if you ever see example code using
`genai.configure()` / `genai.GenerativeModel()`, that's the old package.

Env var required: GEMINI_API_KEY
"""

from __future__ import annotations

import os
from typing import Optional

from google import genai
from google.genai import types

_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add it to .env to use Gemini models."
            )
        _client = genai.Client(api_key=api_key)
    return _client


def generate(
    model: str,
    system_prompt: str,
    user_prompt: str,
    json_mode: bool = False,
    temperature: float = 0.7,
) -> str:
    """Calls a Gemini model and returns the raw text response.

    `model` is the bare Gemini model name (e.g. "gemini-1.5-flash",
    "gemini-1.5-pro") — the "gemini/" provider prefix used elsewhere in
    this codebase is stripped before it gets here.
    """
    client = _get_client()

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=temperature,
        response_mime_type="application/json" if json_mode else "text/plain",
    )

    response = client.models.generate_content(
        model=model,
        contents=user_prompt,
        config=config,
    )
    return response.text
