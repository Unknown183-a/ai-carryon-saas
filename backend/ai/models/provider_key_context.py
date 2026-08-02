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

# (url, token) for the channel's own Upstash Redis database, or None to
# fall back to the platform-wide UPSTASH_REDIS_REST_URL/TOKEN — same
# override-with-fallback shape as gemini/groq above. Set once per run in
# generation_service.py so every ch:{channel_id}:* cache/state read or
# write during that run lands in that channel's own Redis instance
# instead of the single shared one, without threading a parameter through
# every call site in ai/agents/*, ai/rag/embed.py, etc.
redis_credentials_override: contextvars.ContextVar[Optional[tuple[str, str]]] = contextvars.ContextVar(
    "redis_credentials_override", default=None
)

# Channel's own Celery broker rediss:// URL, or None to fall back to the
# platform-wide CELERY_BROKER_URL — same override-with-fallback shape as
# the others above. Set once per run in generation_service.py; read in
# ai/langgraph/graph.py's _enqueue_render to route that run's render
# chain onto the channel's own broker instead of the shared one.
celery_broker_url_override: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "celery_broker_url_override", default=None
)
