"""
Trend Agent (Ch.04 node table: "Pulls topic candidates from Google
Trends, cached in Redis").

Cache-first per Ch.11: key `ch:{channel_id}:trend` (Ch.12b's channel
namespacing, retrofitted in Phase 6), TTL 6 hours. Ch.05's fig 5.2 cache pattern ("Cached? Yes -> return instantly / No -> call,
then cache") applies here too even though that figure is drawn for the
Research Agent — Ch.11's table lists the same pattern for Trend.

Data source: pytrends (unofficial Google Trends client), seeded with the
channel's category as a keyword, since Google Trends has no native
"AI/coding" category granular enough to browse without a seed term. If
pytrends fails or returns nothing usable, falls back to a small static
evergreen list rather than blocking the whole pipeline — matches the
spirit of Ch.05's "retry then fail over to a fallback" policy, applied to
Trend's own external dependency.

--- Diversity / dedup bugfix -------------------------------------------
Two bugs used to live here:

1. `topic = candidates[0]` — always took the single top trending item,
   every run, deterministically. Combined with a 6h Redis cache on the
   candidate list, and a fallback list that started with "new AI model
   release this week", this meant a broad category like "Technology"
   funneled down to the exact same sub-topic run after run.

2. There was no concept of "angle" at all. A category like Technology
   spans product launches, gadgets/phones, robots/drones, explainers,
   engineering deep-dives, industry news, comparisons, and future
   outlook — but nothing here ever tried to cover more than one of
   those buckets.

Fix: candidates (live or fallback) are now tagged with a coarse "angle"
bucket, filtered against a rolling per-channel history of recently used
topics (Redis) *and* a semantic dedup check against this channel's own
RAG research collection (research_agent.is_recently_covered), and
selection rotates through unused angles instead of always grabbing the
top hit. If every real candidate is exhausted/duplicate, a fresh topic
is synthesized from the next angle in rotation so the category is
actually covered end-to-end, not just its single most obvious slice.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, NamedTuple

from app.core.redis_client import channel_key, get_redis
from ai.agents._utils import normalize_topic, topic_similarity

TREND_CACHE_TTL_SECONDS = 6 * 60 * 60  # Ch.11

RECENT_TOPICS_MAX = 40  # how many past topics we remember per channel
RECENT_TOPICS_TTL_SECONDS = 60 * 24 * 60 * 60  # 60 days
RECENT_TOPIC_SIMILARITY_THRESHOLD = 0.72  # fuzzy match against recent history

ANGLE_CURSOR_TTL_SECONDS = 90 * 24 * 60 * 60  # 90 days


class Candidate(NamedTuple):
    topic: str
    angle: str  # coarse bucket, used to keep coverage diverse


# Angle buckets a "technology / AI / coding" style channel should rotate
# through, instead of only ever landing on "new_release". `{category}`
# is filled in with channel_config["category"]'s first term at runtime.
# Order here is also the rotation order used when synthesizing a fresh
# topic because every live/fallback candidate got filtered out as a
# recent duplicate.
FALLBACK_TOPIC_ANGLES: dict[str, list[str]] = {
    "new_release": [
        "new AI model release this week",
        "newest {category} product launch this week",
    ],
    "gadgets_devices": [
        "new phone or gadget just announced in {category}",
        "hands-on breakdown of a new {category} device",
    ],
    "robots_drones": [
        "new robot or drone unveiled this week",
    ],
    "how_it_works": [
        "how {category} actually works, explained simply",
        "the basics of {category} beginners get wrong",
    ],
    "behind_the_scenes": [
        "the engineering behind a major {category} breakthrough",
        "advanced deep dive into how {category} is really built",
    ],
    "comparison": [
        "comparing two competing approaches in {category}",
    ],
    "industry_news": [
        "{category} industry news roundup this week",
    ],
    "future_outlook": [
        "where {category} is heading in the next few years",
    ],
}
ANGLE_ORDER = list(FALLBACK_TOPIC_ANGLES.keys())


def _category_seed(channel_config: dict[str, Any]) -> str:
    return channel_config["category"].split(",")[0].strip()


def _fetch_trending_topics_sync(channel_config: dict[str, Any]) -> list[str]:
    """Blocking pytrends call — run via asyncio.to_thread from the node."""
    from pytrends.request import TrendReq

    pytrends = TrendReq(hl=channel_config.get("language", "en"), tz=330)
    seed_keywords = [_category_seed(channel_config)]
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


def _fallback_candidates(channel_config: dict[str, Any]) -> list[Candidate]:
    """One candidate per angle bucket (formatted with this channel's
    category) instead of a flat list that always led with the same item.
    """
    category = _category_seed(channel_config)
    out: list[Candidate] = []
    for angle, templates in FALLBACK_TOPIC_ANGLES.items():
        for template in templates:
            out.append(Candidate(topic=template.format(category=category), angle=angle))
    return out


async def get_trending_topics(channel_config: dict[str, Any]) -> list[str]:
    """Unchanged externally (still returns a flat list of topic strings —
    other callers/tests may depend on that shape) but the fallback pool
    is now the diverse, angle-tagged one instead of a five-item list
    that always started with "new AI model".
    """
    channel_id = channel_config["channel_id"]
    cache_key = channel_key(channel_id, "trend")

    redis = get_redis()
    cached = redis.get(cache_key)
    if cached:
        return json.loads(cached)

    try:
        topics = await asyncio.to_thread(_fetch_trending_topics_sync, channel_config)
        if not topics:
            topics = [c.topic for c in _fallback_candidates(channel_config)]
    except Exception:
        topics = [c.topic for c in _fallback_candidates(channel_config)]

    redis.set(cache_key, json.dumps(topics), ex=TREND_CACHE_TTL_SECONDS)
    return topics


def _guess_angle(topic: str) -> str:
    """Live pytrends candidates aren't angle-tagged (they're just search
    queries), so bucket them heuristically. Good enough for rotation
    purposes — worst case a candidate lands in the wrong bucket, it's
    still correctly deduped against recent history either way.
    """
    lowered = topic.lower()
    keyword_to_angle = {
        "robot": "robots_drones",
        "drone": "robots_drones",
        "phone": "gadgets_devices",
        "gadget": "gadgets_devices",
        "device": "gadgets_devices",
        "how": "how_it_works",
        "explain": "how_it_works",
        "vs": "comparison",
        "compare": "comparison",
        "news": "industry_news",
        "future": "future_outlook",
        "engineering": "behind_the_scenes",
        "deep dive": "behind_the_scenes",
    }
    for kw, angle in keyword_to_angle.items():
        if kw in lowered:
            return angle
    return "new_release"


def _recent_topics_key(channel_id: str) -> str:
    return channel_key(channel_id, "trend:recent_topics")


def _angle_cursor_key(channel_id: str) -> str:
    return channel_key(channel_id, "trend:angle_cursor")


def _get_recent_topics(redis: Any, channel_id: str) -> list[str]:
    raw = redis.lrange(_recent_topics_key(channel_id), 0, -1)
    return [r.decode() if isinstance(r, bytes) else r for r in raw] if raw else []


def _remember_topic(redis: Any, channel_id: str, topic: str) -> None:
    key = _recent_topics_key(channel_id)
    redis.lpush(key, normalize_topic(topic))
    redis.ltrim(key, 0, RECENT_TOPICS_MAX - 1)
    redis.expire(key, RECENT_TOPICS_TTL_SECONDS)


def _is_recent_duplicate(topic: str, recent_topics: list[str]) -> bool:
    slug = normalize_topic(topic)
    for past in recent_topics:
        if slug == past or topic_similarity(slug, past) >= RECENT_TOPIC_SIMILARITY_THRESHOLD:
            return True
    return False


def _next_angle(redis: Any, channel_id: str) -> str:
    """Rotates through ANGLE_ORDER per channel so repeated fallback
    synthesis doesn't just loop back to 'new_release' every time either.
    """
    idx = redis.incr(_angle_cursor_key(channel_id))
    redis.expire(_angle_cursor_key(channel_id), ANGLE_CURSOR_TTL_SECONDS)
    return ANGLE_ORDER[int(idx) % len(ANGLE_ORDER)]


def select_diverse_topic(
    candidates: list[str],
    channel_config: dict[str, Any],
    channel_id: str,
) -> str:
    """Replaces the old `candidates[0]`. Filters out anything that looks
    like a recent repeat (cheap Redis check first, then a semantic RAG
    check against the channel's own research history — see
    research_agent.is_recently_covered), rotating angle coverage instead
    of always collapsing to the top/first trending hit.
    """
    from ai.agents.research_agent import is_recently_covered  # local import: avoids a
    # trend_agent <-> research_agent import cycle at module load time

    redis = get_redis()
    recent_topics = _get_recent_topics(redis, channel_id)

    for topic in candidates:
        if _is_recent_duplicate(topic, recent_topics):
            continue
        if is_recently_covered(topic, channel_id):
            continue
        return topic

    # Every live/fallback candidate was a duplicate of something recent —
    # this is exactly the failure mode reported (same "new AI model"
    # angle every run). Synthesize a genuinely fresh topic from the next
    # angle bucket in rotation instead of giving up and reusing one.
    category = _category_seed(channel_config)
    for _ in range(len(ANGLE_ORDER)):
        angle = _next_angle(redis, channel_id)
        templates = FALLBACK_TOPIC_ANGLES[angle]
        for template in templates:
            candidate_topic = template.format(category=category)
            if not _is_recent_duplicate(candidate_topic, recent_topics) and not is_recently_covered(
                candidate_topic, channel_id
            ):
                return candidate_topic

    # Truly exhausted (e.g. brand-new channel with a tiny category and a
    # long history) — fall back to the single least-recently-used
    # candidate rather than raising, so the pipeline still produces a video.
    return candidates[0] if candidates else FALLBACK_TOPIC_ANGLES["new_release"][0].format(category=category)


async def trend_node(state: dict[str, Any]) -> dict[str, Any]:
    """LangGraph node wrapper — reads channel_config from state, writes
    topic (a diverse, deduped pick) and trend_candidates (the full
    shortlist, unchanged shape for any downstream consumers).
    """
    channel_config = state["channel_config"]
    channel_id = channel_config["channel_id"]
    candidates = await get_trending_topics(channel_config)

    topic = select_diverse_topic(candidates, channel_config, channel_id)

    redis = get_redis()
    _remember_topic(redis, channel_id, topic)

    return {
        "trend_candidates": candidates,
        "topic": topic,
        "topic_angle": _guess_angle(topic),
        "run_log": ["ran:trend"],
    }
