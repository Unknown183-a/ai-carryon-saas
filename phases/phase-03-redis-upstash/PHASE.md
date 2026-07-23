<!-- Self-contained phase brief. Companion docs: ../../BUILD_GUIDE.md (full build order) and ../../docs/architecture/AI-CarryON-Architecture.html (the why). -->

## Phase 3 — Redis (Upstash)
*(SAD reference: Chapter 11 — Redis)*

**Goal:** the rate limiter middleware from Phase 2 is real, backed by Redis — proving the cache-first pattern works before agents depend on it.

**Depends on:** Phase 2.

**Tasks:**
- [x] `backend/app/core/redis_client.py` — thin wrapper around Upstash REST client with `get`, `set`, `incr`, TTL support
- [x] Wire real rate limiting into `backend/app/api/middleware/rate_limit.py` using key prefix `rl:*` (Ch.11 table) and a 60-second TTL
- [x] Confirm the 429 response fires after the configured request budget is exceeded
- [x] Leave the namespacing (`ch:{channel_id}:*`) as a TODO comment — real multi-tenant namespacing happens in Phase 6, don't build it early

**Definition of Done:** hammering the `/health` endpoint past the rate limit returns `429`; waiting past the TTL resets it.

**Handoff Notes:**
> Redis client (`redis_client.py`) talks to Upstash over its REST API (`httpx`, one POST per command) rather than `redis-py` over TCP — matches the phase brief's "Upstash REST client" wording and needs no connection pooling. `rate_limit.py` keys the fixed-window counter by Firebase uid (unverified JWT decode — full verification stays in `dependencies.get_current_user`, this just needs a stable bucket) when a Bearer token is present, falling back to client IP for anonymous routes like `/health`. Budget defaults to 30 req/60s, overridable via `RATE_LIMIT_REQUESTS_PER_MINUTE` env var. `ch:{channel_id}:*` namespacing left as TODO comments in both files per this brief — do not build early. Verified against a fake in-memory Upstash server (`tests/phase3_redis_ratelimit_test.py`, no real Upstash account needed to test): budget-worth of requests succeed, the next one gets `429` with a `Retry-After` header, repeated requests inside the window stay limited, and force-expiring the TTL resets the window. Also added `backend/requirements.txt` (didn't exist yet) since deps had only ever been installed ad hoc through Phase 2.
>
> **Not yet done / left for whoever picks this up:** the fake-server test proves the logic; nobody has run this against a real Upstash database yet (no Upstash account created — still unchecked in `STATUS.md`'s prerequisites). Before calling this fully verified against production Redis, create the free Upstash DB, drop the REST URL/token into `.env`, and re-run against the real service.

---
