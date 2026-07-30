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
FACTUAL_TOPIC_ANGLES: dict[str, list[str]] = {
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

# --- Narrative-mode angle pool -------------------------------------
# The factual pool above assumes there's a real-world thing to chase —
# a release, a device, an industry. A fiction/story channel has none of
# that; "newest Hindi Interactive Stories, Mystery, Horror product
# launch this week" (a real fallback candidate the old single pool
# would have produced for that category) is nonsense as a story seed.
# These buckets are genre/trope angles instead — the same rotation,
# recency-dedup, and dead-letter-synthesis machinery below applies
# unchanged, it's just fed a pool that actually fits fiction.
NARRATIVE_TOPIC_ANGLES: dict[str, list[str]] = {
    "mystery_twist": [
        "a {category} short with a mystery that flips in the final line",
        "someone discovers a hidden truth about a person they trust, {category} style",
    ],
    "horror_supernatural": [
        "a {category} short built around a supernatural warning ignored too late",
        "an ordinary night that turns eerie, {category} style",
    ],
    "moral_dilemma": [
        "a {category} short where the protagonist must choose between two people they love",
        "a small lie in a {category} story that spirals out of control",
    ],
    "revenge_justice": [
        "a {category} short about quiet revenge finally being served",
        "someone wronged years ago gets one chance to set it right, {category} style",
    ],
    "family_secret": [
        "a {category} short where a family secret surfaces at a reunion",
        "a letter or object reveals a parent's hidden past, {category} style",
    ],
    "love_betrayal": [
        "a {category} short about a betrayal disguised as an act of love",
        "two people separated by a misunderstanding neither will admit to, {category} style",
    ],
    "crime_investigation": [
        "a {category} short where an amateur notices what the investigators missed",
        "a small clue unravels a bigger crime, {category} style",
    ],
}

# Which pool + rotation order a channel uses. Keyed by content_type so
# adding a third content_type later means adding one more entry here,
# not a channel-specific branch — and a channel can still supply its
# own pool via channel_config["topic_angles"] (same {angle: [templates]}
# shape) without any code change at all, for a genre this pool doesn't
# cover yet.
CONTENT_TYPE_ANGLE_POOLS: dict[str, dict[str, list[str]]] = {
    "factual": FACTUAL_TOPIC_ANGLES,
    "narrative": NARRATIVE_TOPIC_ANGLES,
}
DEFAULT_ANGLE_POOL_CONTENT_TYPE = "factual"

# Back-compat alias — some callers/tests may still import the old name.
FALLBACK_TOPIC_ANGLES = FACTUAL_TOPIC_ANGLES


def _angle_pool(channel_config: dict[str, Any]) -> dict[str, list[str]]:
    """Resolves the angle pool a channel rotates through: an explicit
    per-channel override (channel_config["topic_angles"], plain
    Firestore data) wins if present, otherwise the pool for this
    channel's content_type, defaulting to the factual pool so every
    channel that predates content_type keeps its old behavior exactly.
    """
    override = channel_config.get("topic_angles")
    if override:
        return override
    content_type = channel_config.get("content_type", DEFAULT_ANGLE_POOL_CONTENT_TYPE)
    return CONTENT_TYPE_ANGLE_POOLS.get(content_type, FACTUAL_TOPIC_ANGLES)


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
    Pool is resolved per-channel (see _angle_pool) so a narrative channel
    gets genre/trope angles instead of tech-release angles, and a
    channel with its own `topic_angles` override gets exactly that.
    """
    category = _category_seed(channel_config)
    out: list[Candidate] = []
    for angle, templates in _angle_pool(channel_config).items():
        for template in templates:
            out.append(Candidate(topic=template.format(category=category), angle=angle))
    return out


async def get_trending_topics(channel_config: dict[str, Any]) -> list[str]:
    """Unchanged externally (still returns a flat list of topic strings —
    other callers/tests may depend on that shape) but the fallback pool
    is now the diverse, angle-tagged one instead of a five-item list
    that always started with "new AI model".

    Narrative channels skip the pytrends call entirely: Google Trends
    has no meaningful signal for "what's trending in Hindi horror
    shorts" the way it does for a tech/news category, so seeding it with
    a fiction category just burns a call to come back empty (or with
    unrelated web-search-style queries) before falling through to the
    same fallback path anyway. Going straight to angle synthesis is
    faster and no less diverse, since that's genre rotation, not a
    "what's trending" answer to begin with.
    """
    channel_id = channel_config["channel_id"]
    cache_key = channel_key(channel_id, "trend")

    redis = get_redis()
    cached = redis.get(cache_key)
    if cached:
        return json.loads(cached)

    if channel_config.get("content_type") == "narrative":
        topics = [c.topic for c in _fallback_candidates(channel_config)]
    else:
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


def _next_angle(redis: Any, channel_id: str, angle_order: list[str]) -> str:
    """Rotates through this channel's own angle order so repeated
    fallback synthesis doesn't just loop back to the first angle every
    time either. `angle_order` comes from the caller's resolved pool
    (factual/narrative/override) — kept as a param rather than a module
    global now that more than one pool exists.
    """
    idx = redis.incr(_angle_cursor_key(channel_id))
    redis.expire(_angle_cursor_key(channel_id), ANGLE_CURSOR_TTL_SECONDS)
    return angle_order[int(idx) % len(angle_order)]


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
    pool = _angle_pool(channel_config)
    angle_order = list(pool.keys())
    for _ in range(len(angle_order)):
        angle = _next_angle(redis, channel_id, angle_order)
        templates = pool[angle]
        for template in templates:
            candidate_topic = template.format(category=category)
            if not _is_recent_duplicate(candidate_topic, recent_topics) and not is_recently_covered(
                candidate_topic, channel_id
            ):
                return candidate_topic

    # Truly exhausted (e.g. brand-new channel with a tiny category and a
    # long history) — fall back to the single least-recently-used
    # candidate rather than raising, so the pipeline still produces a video.
    first_angle = angle_order[0]
    return candidates[0] if candidates else pool[first_angle][0].format(category=category)


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
