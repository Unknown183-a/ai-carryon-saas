"""
Research Agent (Ch.05, RAG wired in Phase 5 per Ch.09/fig 5.1): Topic ->
Redis cache -> Web Search + Qdrant Retriever -> LLM Context Builder ->
Research Summary -> write the new summary back into Qdrant.

Cache-first per Ch.11: key `ch:{channel_id}:research:{normalized_topic}`
(Ch.12b's channel namespacing, retrofitted in Phase 6), TTL 24 hours. A cache hit skips web search, RAG retrieval, and the LLM
call entirely — it's already a finished, previously-grounded summary.

On a cache miss (fig 5.1's full path): web search runs alongside a
hybrid-search RAG retrieval against this channel's own `research` and
`knowledge` Qdrant collections (Ch.10), and both are handed to the LLM
together so the summary can ground itself in either. After a fresh
summary is produced, it's chunked, embedded, and upserted into the
`research` collection (Ch.10: "research: Research summaries per topic")
so the *next* run on this or a related topic has it to retrieve —
closing the loop Ch.20 describes for lessons_learned, but starting here
for raw research.

Retries (Ch.05's table): web search and the LLM summarization call each
retry twice with exponential backoff before the node fails over to a
cached fallback summary if one exists for this exact topic, even stale;
otherwise the node raises and the run is marked failed. RAG retrieval
failures do NOT fail the node — a Qdrant outage degrades this agent back
to web-search-only grounding (Ch.16's Health Agent table: "Qdrant down:
Research Agent falls back to web search only; alert raised" — the alert
side of that is Phase 10's job, not this agent's).
"""

from __future__ import annotations

import re
from typing import Any

from app.core.redis_client import channel_key, get_redis
from ai.agents._utils import retry_with_backoff
from ai.models.llm_client import call_llm, DEFAULT_MODELS
from ai.prompts.prompt_library import research_summarizer_prompt
from ai.rag.retriever import RetrievedChunk, hybrid_search, store_chunks
from ai.tools.web_search import web_search, SearchResult

RESEARCH_CACHE_TTL_SECONDS = 24 * 60 * 60  # Ch.11
STALE_FALLBACK_SUFFIX = ":last_known_good"  # never expires — see get_research_summary
RETRIEVED_CHUNKS_PER_COLLECTION = 3
RAG_COLLECTIONS = ["research", "knowledge"]


def _normalize_topic(topic: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return slug[:80]


def _format_results_for_prompt(results: list[SearchResult]) -> str:
    lines = []
    for i, r in enumerate(results, start=1):
        lines.append(f"{i}. {r.title}\n   {r.snippet}\n   {r.link}")
    return "\n".join(lines) if lines else "(no search results returned)"


def _source_label(collection: str, metadata: dict[str, Any]) -> str:
    if collection == "research":
        return f"past research on '{metadata.get('topic', 'unknown topic')}' ({metadata.get('date', 'undated')})"
    return f"{collection} entry ({metadata.get('domain', metadata.get('date', 'undated'))})"


def _retrieve_context(topic: str, channel_id: str) -> tuple[str, list[RetrievedChunk]]:
    """Runs hybrid search across every RAG collection this agent draws
    on, formats the hits into a labeled prompt section, and also returns
    the raw chunks (used only for logging/debugging, not required by the
    LLM call). Never raises — a retrieval failure on any one collection
    is swallowed and that collection just contributes nothing, since a
    cold or briefly-unavailable Qdrant shouldn't fail the whole run.
    """
    all_chunks: list[tuple[str, RetrievedChunk]] = []
    for collection in RAG_COLLECTIONS:
        try:
            hits = hybrid_search(
                topic, collection=collection, channel_id=channel_id, limit=RETRIEVED_CHUNKS_PER_COLLECTION
            )
            all_chunks.extend((collection, h) for h in hits)
        except Exception:
            continue

    if not all_chunks:
        return "(no relevant retrieved context for this channel yet)", []

    lines = []
    for collection, chunk in all_chunks:
        label = _source_label(collection, chunk.metadata)
        lines.append(f"[Retrieved: {label}]\n{chunk.text}")
    return "\n\n".join(lines), [c for _, c in all_chunks]


async def get_research_summary(topic: str, channel_config: dict[str, Any]) -> tuple[str, list[str]]:
    """Returns (summary, source_links). Cache-first, then web search +
    RAG retrieval + LLM, with a stale-cache fallback if the live path
    fails entirely.
    """
    channel_id = channel_config["channel_id"]
    topic_slug = _normalize_topic(topic)
    cache_key = channel_key(channel_id, f"research:{topic_slug}")
    fallback_key = cache_key + STALE_FALLBACK_SUFFIX

    redis = get_redis()
    cached = redis.get(cache_key)
    if cached:
        import json
        parsed = json.loads(cached)
        return parsed["summary"], parsed["sources"]

    try:
        results = retry_with_backoff(lambda: web_search(topic, num_results=6), attempts=3)
        retrieved_context, _chunks = _retrieve_context(topic, channel_id)

        def _summarize() -> str:
            return call_llm(
                model=DEFAULT_MODELS["research"],
                system_prompt=research_summarizer_prompt(channel_config),
                user_prompt=(
                    f"Topic: {topic}\n\n"
                    f"Search results:\n{_format_results_for_prompt(results)}\n\n"
                    f"Retrieved context:\n{retrieved_context}"
                ),
            )

        summary = retry_with_backoff(_summarize, attempts=3)
        sources = [r.link for r in results if r.link]

        import json
        payload = json.dumps({"summary": summary, "sources": sources})
        redis.set(cache_key, payload, ex=RESEARCH_CACHE_TTL_SECONDS)
        redis.set(fallback_key, payload)  # no TTL — last-known-good, per Ch.05's fallback policy

        _write_back(summary, topic, channel_id, sources)

        return summary, sources

    except Exception:
        stale = redis.get(fallback_key)
        if stale:
            import json
            parsed = json.loads(stale)
            return parsed["summary"], parsed["sources"]
        raise


def _write_back(summary: str, topic: str, channel_id: str, sources: list[str]) -> None:
    """Stores the freshly-generated summary into Qdrant's `research`
    collection so future runs can retrieve it (see module docstring).
    Best-effort: a write-back failure shouldn't fail a run that already
    successfully produced its summary — it just means this run's summary
    won't be retrievable by future runs, which is a degradation, not a
    correctness problem for THIS run.
    """
    import datetime

    try:
        store_chunks(
            "research",
            summary,
            metadata={
                "channel_id": channel_id,
                "topic": topic,
                "source_urls": sources,
                "date": datetime.date.today().isoformat(),
            },
        )
    except Exception:
        pass


async def research_node(state: dict[str, Any]) -> dict[str, Any]:
    channel_config = state["channel_config"]
    topic = state["topic"]
    summary, sources = await get_research_summary(topic, channel_config)
    return {
        "research_summary": summary,
        "research_sources": sources,
        "run_log": ["ran:research"],
    }
