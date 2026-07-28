"""
Per-run LLM provider key overrides (new -- closes the TODO in
llm_client.py: "per-channel model preference resolution... Not built
now on purpose").

A ContextVar (not a plain module global or a parameter threaded through
every one of call_llm()'s ~13 agent call-sites): set once at the top of
run_generation() and visible to every call_llm() -> provider client
call for that async task's duration, without touching a single agent
file.
"""

from __future__ import annotations

import contextvars
from typing import Optional

gemini_key_override: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "gemini_key_override", default=None
)
groq_key_override: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "groq_key_override", default=None
)
