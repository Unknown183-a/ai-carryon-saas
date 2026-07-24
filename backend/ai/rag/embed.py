"""
Embedding client (Ch.09): text -> vector, via the Gemini embedding
model, Redis-cached per Ch.11's table (`embed:*`, 7 days).

Same cache-first shape as research_agent.py's Redis usage — the cache
key is a hash of the exact text plus task_type, since two different
task_types for the same text produce different (asymmetric) embeddings
and must not share a cache entry.

Retries: per Ch.05's stated policy ("web search and embedding calls
retry twice with exponential backoff"), this wraps the raw Gemini call
in the same `retry_with_backoff` helper the Research Agent uses.
"""

from __future__ import annotations

import hashlib
import json

from app.core.redis_client import get_redis
from ai.agents._utils import retry_with_backoff
from integrations.gemini import client as gemini_client

EMBED_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60  # Ch.11: embed:*, 7 days


def _cache_key(text: str, task_type: str) -> str:
    digest = hashlib.sha256(f"{task_type}:{text}".encode("utf-8")).hexdigest()
    return f"embed:{digest}"


def embed_text(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    """Returns an embedding vector for `text`, checking Redis first.

    `task_type` must be "RETRIEVAL_DOCUMENT" for text being stored
    (chunks going into Qdrant) or "RETRIEVAL_QUERY" for a search query —
    see integrations/gemini/client.py's `embed()` docstring for why the
    distinction matters.
    """
    redis = get_redis()
    key = _cache_key(text, task_type)

    cached = redis.get(key)
    if cached:
        return json.loads(cached)

    vector = retry_with_backoff(lambda: gemini_client.embed(text, task_type=task_type), attempts=3)

    redis.set(key, json.dumps(vector), ex=EMBED_CACHE_TTL_SECONDS)
    return vector


def embed_batch(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """Embeds several texts. Gemini's embed_content only accepts one
    input per request for this model (see integrations/gemini/client.py),
    so this is a plain loop over `embed_text` — the per-text Redis cache
    still avoids re-embedding anything already seen.
    """
    return [embed_text(text, task_type=task_type) for text in texts]
