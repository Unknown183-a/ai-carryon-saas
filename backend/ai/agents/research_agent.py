"""
Research Agent (Ch.05): Topic -> Redis cache -> Web Search -> LLM Context
Builder -> Research Summary. RAG/Qdrant retrieval is deferred to Phase 5
per this phase's brief ("use plain web search for now") — so the fig 5.1
pipeline runs with Serper standing in for the Qdrant Retriever step.

Cache-first per Ch.11: key `research:{channel_id}:{normalized_topic}`,
TTL 24 hours.

Retries (Ch.05's table): web search and the LLM summarization call each
retry twice with exponential backoff before the node fails over to a
cached fallback summary if one exists for this exact topic, even stale;
otherwise the node raises and the run is marked failed.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.redis_client import get_redis
from ai.agents._utils import retry_with_backoff
from ai.models.llm_client import call_llm, DEFAULT_MODELS
from ai.prompts.prompt_library import research_summarizer_prompt
from ai.tools.web_search import web_search, SearchResult

RESEARCH_CACHE_TTL_SECONDS = 24 * 60 * 60  # Ch.11
STALE_FALLBACK_SUFFIX = ":last_known_good"  # never expires — see get_research_summary


def _normalize_topic(topic: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return slug[:80]


def _format_results_for_prompt(results: list[SearchResult]) -> str:
    lines = []
    for i, r in enumerate(results, start=1):
        lines.append(f"{i}. {r.title}\n   {r.snippet}\n   {r.link}")
    return "\n".join(lines) if lines else "(no search results returned)"


async def get_research_summary(topic: str, channel_config: dict[str, Any]) -> tuple[str, list[str]]:
    """Returns (summary, source_links). Cache-first, then web search + LLM,
    with a stale-cache fallback if the live path fails entirely.
    """
    channel_id = channel_config["channel_id"]
    topic_slug = _normalize_topic(topic)
    cache_key = f"research:{channel_id}:{topic_slug}"
    fallback_key = cache_key + STALE_FALLBACK_SUFFIX

    redis = get_redis()
    cached = redis.get(cache_key)
    if cached:
        import json
        parsed = json.loads(cached)
        return parsed["summary"], parsed["sources"]

    try:
        results = retry_with_backoff(lambda: web_search(topic, num_results=6), attempts=3)

        def _summarize() -> str:
            return call_llm(
                model=DEFAULT_MODELS["research"],
                system_prompt=research_summarizer_prompt(channel_config),
                user_prompt=(
                    f"Topic: {topic}\n\nSearch results:\n{_format_results_for_prompt(results)}"
                ),
            )

        summary = retry_with_backoff(_summarize, attempts=3)
        sources = [r.link for r in results if r.link]

        import json
        payload = json.dumps({"summary": summary, "sources": sources})
        redis.set(cache_key, payload, ex=RESEARCH_CACHE_TTL_SECONDS)
        redis.set(fallback_key, payload)  # no TTL — last-known-good, per Ch.05's fallback policy
        return summary, sources

    except Exception:
        stale = redis.get(fallback_key)
        if stale:
            import json
            parsed = json.loads(stale)
            return parsed["summary"], parsed["sources"]
        raise


async def research_node(state: dict[str, Any]) -> dict[str, Any]:
    channel_config = state["channel_config"]
    topic = state["topic"]
    summary, sources = await get_research_summary(topic, channel_config)
    return {
        "research_summary": summary,
        "research_sources": sources,
        "run_log": ["ran:research"],
    }
