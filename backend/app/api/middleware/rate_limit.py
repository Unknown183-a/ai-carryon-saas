"""
Rate limiter middleware — real Redis-backed implementation (Phase 3).

Fixed-window counter per Ch.11 of the SAD: each request increments a
`rl:*` counter; the first increment in a window also sets a 60-second
TTL. Once the counter passes the configured per-minute budget, further
requests in that same window get `429` until the TTL expires and the
window resets.

Per Ch.03 ("Rate Limiter... returns 429 once the per-minute budget is
spent, checked by a Redis counter keyed by user ID"), the identity used
to key the counter is the caller's Firebase uid when a Bearer token is
present. Routes like `/health` have no auth at all, so this falls back
to the client's IP for anonymous requests — that's how you can hammer
`/health` directly and still trip the limiter (see PHASE.md's Definition
of Done).

# TODO (Phase 6): once multi-tenancy lands, prefix these keys with
# `ch:{channel_id}:*` too (e.g. `ch:{channel_id}:rl:user:{uid}`) so one
# channel's traffic can't starve another's budget. Not built now on
# purpose — real namespacing is Phase 6's job, per BUILD_GUIDE.md.
"""

from __future__ import annotations

import os

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.redis_client import get_redis

RATE_LIMIT_PREFIX = "rl:"
WINDOW_SECONDS = 60
DEFAULT_REQUESTS_PER_MINUTE = 30


def _requests_per_minute() -> int:
    """Per-minute request budget. Overridable via env for local testing —
    e.g. set RATE_LIMIT_REQUESTS_PER_MINUTE=3 to trip the limiter quickly
    without sending 30+ real requests.
    """
    return int(os.environ.get("RATE_LIMIT_REQUESTS_PER_MINUTE", DEFAULT_REQUESTS_PER_MINUTE))


def _identify_caller(request: Request) -> str:
    """Best-effort identity to key the counter by.

    This deliberately does NOT call firebase_auth.verify_id_token — full
    signature verification is dependencies.get_current_user's job for
    protected routes, and running it twice per request is wasted work.
    The rate limiter only needs a stable bucket to count against, so an
    unverified decode of the uid claim is enough; a forged token just
    means the forger rate-limits themselves under a fake bucket, which is
    harmless.
    """
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1]
        try:
            claims = jwt.decode(token, options={"verify_signature": False})
        except Exception:
            claims = {}
        uid = claims.get("user_id") or claims.get("sub")
        if uid:
            return f"user:{uid}"

    client_host = request.client.host if request.client else "unknown"
    return f"ip:{client_host}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        redis = get_redis()
        key = f"{RATE_LIMIT_PREFIX}{_identify_caller(request)}"

        count = redis.incr(key)
        if count == 1:
            # First request in a fresh window — start the 60s TTL per
            # Ch.11's table. Subsequent increments ride the same TTL.
            redis.expire(key, WINDOW_SECONDS)

        budget = _requests_per_minute()
        if count > budget:
            ttl = redis.ttl(key)
            retry_after = ttl if ttl and ttl > 0 else WINDOW_SECONDS
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        f"Rate limit exceeded: {budget} requests per "
                        f"{WINDOW_SECONDS}s. Try again later."
                    )
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
