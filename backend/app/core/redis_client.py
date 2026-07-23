"""
Thin wrapper around the Upstash Redis REST API.

Upstash exposes Redis over plain HTTPS (one request in, one JSON result
back) instead of the usual TCP protocol — no persistent connection or
connection pool to manage, which fits FastAPI's request/response cycle
and works fine from any host that can make outbound HTTPS calls.

Env vars required:
    UPSTASH_REDIS_REST_URL
    UPSTASH_REDIS_REST_TOKEN

Usage:
    from app.core.redis_client import get_redis

    redis = get_redis()
    redis.set("trend:cricket", "...", ex=6 * 60 * 60)
    redis.get("trend:cricket")
    redis.incr("rl:user:abc123")

Every key in this project is namespaced by prefix per Ch.11 of the SAD
(trend:*, research:*, llm:*, prompt:*, embed:*, sess:*, rl:*, api:*).

# TODO (Phase 6): once multi-tenancy lands, every key everywhere in the
# codebase gets retrofitted to `ch:{channel_id}:*` — don't build that
# namespacing early, it belongs to Phase 6 per BUILD_GUIDE.md.
"""

from __future__ import annotations

import os
from typing import Optional

import httpx


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

    def expire(self, key: str, seconds: int) -> None:
        """Sets (or resets) a TTL on an existing key."""
        self._command("EXPIRE", key, seconds)

    def ttl(self, key: str) -> int:
        """Seconds until `key` expires. -1 = no TTL set, -2 = key doesn't exist."""
        return int(self._command("TTL", key))

    def delete(self, key: str) -> None:
        self._command("DEL", key)


_client: Optional[RedisClient] = None


def get_redis() -> RedisClient:
    """Returns a shared, lazily-created RedisClient. One instance per
    process is enough — httpx.Client already pools connections internally.
    """
    global _client
    if _client is None:
        _client = RedisClient()
    return _client
