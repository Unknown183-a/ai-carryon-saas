<!-- Self-contained phase brief. Companion docs: ../../BUILD_GUIDE.md (full build order) and ../../docs/architecture/AI-CarryON-Architecture.html (the why). -->

## Phase 3 — Redis (Upstash)
*(SAD reference: Chapter 11 — Redis)*

**Goal:** the rate limiter middleware from Phase 2 is real, backed by Redis — proving the cache-first pattern works before agents depend on it.

**Depends on:** Phase 2.

**Tasks:**
- [ ] `backend/app/core/redis_client.py` — thin wrapper around Upstash REST client with `get`, `set`, `incr`, TTL support
- [ ] Wire real rate limiting into `backend/app/api/middleware/rate_limit.py` using key prefix `rl:*` (Ch.11 table) and a 60-second TTL
- [ ] Confirm the 429 response fires after the configured request budget is exceeded
- [ ] Leave the namespacing (`ch:{channel_id}:*`) as a TODO comment — real multi-tenant namespacing happens in Phase 6, don't build it early

**Definition of Done:** hammering the `/health` endpoint past the rate limit returns `429`; waiting past the TTL resets it.

**Handoff Notes:**
> _(empty — fill in if you stop here)_

---
