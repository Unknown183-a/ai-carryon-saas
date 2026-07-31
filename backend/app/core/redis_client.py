"""
Thin wrapper around the Upstash Redis REST API.

Upstash exposes Redis over plain HTTPS (one request in, one JSON result
back) instead of the usual TCP protocol — no persistent connection or
connection pool to manage, which fits FastAPI's request/response cycle
and works fine from any host that can make outbound HTTPS calls.

Env vars required (platform default, used when a channel has no Redis
override set — see below):
    UPSTASH_REDIS_REST_URL
    UPSTASH_REDIS_REST_TOKEN

Usage:
    from app.core.redis_client import get_redis

    redis = get_redis()
    redis.set("trend:cricket", "...", ex=6 * 60 * 60)
    redis.get("trend:cricket")
    redis.incr("rl:user:abc123")

Every key in this project is namespaced by prefix per Ch.11 of the SAD
(trend:*, research:*, llm:*, prompt:*, embed:*, sess:*, rl:*, api:*), and
— per Ch.12b, done in Phase 6 — every one of those that's actually
scoped to one channel is further prefixed `ch:{channel_id}:` via the
`channel_key()` helper below, so one Redis instance behaves like many
logically-isolated caches. A lookup for the wrong channel simply misses;
there is no cross-channel key collision to guard against separately.
Not every key in this codebase is channel-scoped — the rate limiter's
per-user budget (`rl:user:{uid}`) intentionally is not, since it exists
to protect the whole API's capacity, not one channel's; see
app/api/middleware/rate_limit.py's docstring for that decision and the
narrower per-channel counter it adds alongside the per-user one.

Per-channel Redis (added after all channels sharing one free-tier
Upstash database burned through its combined 500K commands/month cap in
~4-5 days): a channel can supply its own Upstash `redis_rest_url` /
`redis_rest_token` via the Providers screen, same as its own Gemini/Groq
key. `get_redis()` picks up that channel's credentials automatically
during a pipeline run via `redis_credentials_override`
(ai/models/provider_key_context.py) — same override-with-fallback shape
gemini/groq clients already use — so every call site below keeps calling
plain `get_redis()` with no changes. A channel with no Redis key of its
own keeps landing on the shared platform database, same as today.
"""

from __future__ import annotations

import os
from typing import Optional

import httpx

from ai.models.provider_key_context import redis_credentials_override


def channel_key(channel_id: str, suffix: str) -> str:
    """Builds a channel-namespaced Redis key: `ch:{channel_id}:{suffix}`
    (Ch.12b). Every cache key that's scoped to one channel's data should
    be built through this, not by hand, so there's exactly one place
    that defines the namespacing convention.
    """
    return f"ch:{channel_id}:{suffix}"


class RedisClient:
    """A minimal synchronous client for the subset of Redis commands this
    project needs: get, set (with optional TTL), incr, expire, ttl, delete.
    """

    def __init__(self, url: Optional[str] = None, token: Optional[str] = None):
        base_url = url or os.environ["UPSTASH_REDIS_REST_URL"]
        auth_token = token or os.environ["UPSTASH_REDIS_REST_TOKEN"]

        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=5.0,
        )

    def _command(self, *parts: object) -> object:
        """Sends a single Redis command via Upstash's REST pipeline-of-one
        form: POST / with the command + args as a JSON array. Returns the
        `result` field, or raises for any transport/HTTP error.
        """
        response = self._client.post("/", json=list(parts))
        response.raise_for_status()
        body = response.json()
        if body.get("error"):
            raise RuntimeError(f"Redis error for {parts[0]}: {body['error']}")
        return body.get("result")

    def get(self, key: str) -> Optional[str]:
        return self._command("GET", key)

    def set(self, key: str, value: str, ex: Optional[int] = None) -> None:
        """Sets `key` to `value`. If `ex` is given, the key expires after
        `ex` seconds (matches the TTL column in Ch.11's cache table).
        """
        if ex is not None:
            self._command("SET", key, value, "EX", ex)
        else:
            self._command("SET", key, value)

    def incr(self, key: str) -> int:
        """Atomically increments `key` by 1 and returns the new value.
        Redis auto-creates the key at 0 (then 1) if it doesn't exist yet —
        exactly the fixed-window counter behavior the rate limiter needs.
        """
        return int(self._command("INCR", key))

    def lrange(self, key: str, start: int, end: int) -> list:
        result = self._command("LRANGE", key, start, end)
        return result or []

    def lpush(self, key: str, value: str) -> int:
        return self._command("LPUSH", key, value)

    def ltrim(self, key: str, start: int, end: int) -> None:
        self._command("LTRIM", key, start, end)

    def expire(self, key: str, seconds: int) -> None:
        """Sets (or resets) a TTL on an existing key."""
        self._command("EXPIRE", key, seconds)

    def ttl(self, key: str) -> int:
        """Seconds until `key` expires. -1 = no TTL set, -2 = key doesn't exist."""
        return int(self._command("TTL", key))

    def delete(self, key: str) -> None:
        self._command("DEL", key)


_platform_client: Optional[RedisClient] = None
_channel_clients: dict[tuple[str, str], RedisClient] = {}


def get_redis() -> RedisClient:
    """Returns the right RedisClient for the current context.

    If a channel's own Upstash credentials are set on
    `redis_credentials_override` (generation_service.py does this for the
    duration of that channel's pipeline run), returns a client for that
    channel's own database — cached per (url, token) pair across calls so
    a run's several dozen cache touches share one httpx.Client instead of
    opening a new one each time. Otherwise falls back to the single
    shared platform client (lazily created, one per process), exactly as
    before this override existed.
    """
    override = redis_credentials_override.get()
    if override is not None:
        if override not in _channel_clients:
            url, token = override
            _channel_clients[override] = RedisClient(url=url, token=token)
        return _channel_clients[override]

    global _platform_client
    if _platform_client is None:
        _platform_client = RedisClient()
    return _platform_client
