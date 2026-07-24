"""
Trend Agent (Ch.04 node table: "Pulls topic candidates from Google
Trends, cached in Redis").

Cache-first per Ch.11: key `trend:{channel_id}`, TTL 6 hours. Ch.05's
fig 5.2 cache pattern ("Cached? Yes -> return instantly / No -> call,
then cache") applies here too even though that figure is drawn for the
Research Agent — Ch.11's table lists the same pattern for Trend.

Data source: pytrends (unofficial Google Trends client), seeded with the
channel's category as a keyword, since Google Trends has no native
"AI/coding" category granular enough to browse without a seed term. If
pytrends fails or returns nothing usable, falls back to a small static
evergreen list rather than blocking the whole pipeline — matches the
spirit of Ch.05's "retry then fail over to a fallback" policy, applied to
Trend's own external dependency.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.core.redis_client import get_redis

TREND_CACHE_TTL_SECONDS = 6 * 60 * 60  # Ch.11

# Used only if pytrends fails after retries — evergreen topics for an
# AI/coding/future-tech channel, not a substitute for real trend data.
FALLBACK_TOPICS = [
    "new AI model release this week",
    "AI coding assistant comparison",
    "how large language models actually work",
    "AI tool that saves developers time",
    "future of AI in software engineering",
]


def _fetch_trending_topics_sync(channel_config: dict[str, Any]) -> list[str]:
    """Blocking pytrends call — run via asyncio.to_thread from the node."""
    from pytrends.request import TrendReq

    pytrends = TrendReq(hl=channel_config.get("language", "en"), tz=330)
    seed_keywords = [channel_config["category"].split(",")[0].strip()]
    pytrends.build_payload(seed_keywords, timeframe="now 7-d")

    related = pytrends.related_queries()
    topics: list[str] = []
    for keyword_results in related.values():
        rising = keyword_results.get("rising")
        if rising is not None and not rising.empty:
            topics.extend(rising["query"].tolist())
        top = keyword_results.get("top")
        if top is not None and not top.empty:
            topics.extend(top["query"].tolist())

    # De-dupe, keep order
    seen: set[str] = set()
    deduped = []
    for t in topics:
        if t not in seen:
            seen.add(t)
            deduped.append(t)
    return deduped[:10]


async def get_trending_topics(channel_config: dict[str, Any]) -> list[str]:
    channel_id = channel_config["channel_id"]
    cache_key = f"trend:{channel_id}"

    redis = get_redis()
    cached = redis.get(cache_key)
    if cached:
        return json.loads(cached)

    try:
        topics = await asyncio.to_thread(_fetch_trending_topics_sync, channel_config)
        if not topics:
            topics = FALLBACK_TOPICS
    except Exception:
        topics = FALLBACK_TOPICS

    redis.set(cache_key, json.dumps(topics), ex=TREND_CACHE_TTL_SECONDS)
    return topics


async def trend_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node wrapper — reads channel_config from state, writes
    topic (the top candidate) and trend_candidates (the full shortlist).
    """
    channel_config = state["channel_config"]
    candidates = await get_trending_topics(channel_config)
    topic = candidates[0] if candidates else FALLBACK_TOPICS[0]
    return {
        "trend_candidates": candidates,
        "topic": topic,
        "run_log": ["ran:trend"],
    }
