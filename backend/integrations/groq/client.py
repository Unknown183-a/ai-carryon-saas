"""
Thin Groq API client — auth, request formatting, the actual HTTP call.

Same split as backend/integrations/gemini/client.py: no model-selection
logic here, just "given a model name someone already picked, call Groq."

Env var required: GROQ_API_KEY
"""

from __future__ import annotations

import os
from typing import Optional

from groq import Groq

from ai.models.provider_key_context import groq_key_override

_client: Optional[Groq] = None


def _get_client() -> Groq:
    override = groq_key_override.get()
    if override:
        return Groq(api_key=override)

    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Add it to .env to use Groq models."
            )
        _client = Groq(api_key=api_key)
    return _client


def generate(
    model: str,
    system_prompt: str,
    user_prompt: str,
    json_mode: bool = False,
    temperature: float = 0.7,
) -> str:
    """Calls a Groq model and returns the raw text response.

    `model` is the bare Groq model name (e.g. "llama-3.3-70b-versatile") —
    the "groq/" provider prefix used elsewhere in this codebase is
    stripped before it gets here.
    """
    client = _get_client()

    kwargs: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    completion = client.chat.completions.create(**kwargs)
    return completion.choices[0].message.content
