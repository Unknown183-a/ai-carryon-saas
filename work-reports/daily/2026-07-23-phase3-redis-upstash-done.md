# Work Report — 2026-07-23

**Phase worked on:** Phase 3 — Redis (Upstash)
**Author:** Claude
**Time spent:** ~1 hr

## What I built / did

- `backend/app/core/redis_client.py` — `RedisClient` wrapping Upstash's REST API (`httpx`, one POST per command) with `get`, `set` (optional `ex` TTL), `incr`, `expire`, `ttl`, `delete`, plus a lazily-created shared instance via `get_redis()`.
- `backend/app/api/middleware/rate_limit.py` — replaced the Phase 2 stub with a real `RateLimitMiddleware`: fixed-window counter keyed `rl:{identity}`, 60s TTL set on the first increment in a window, `429` with a `Retry-After` header once the per-minute budget is spent. Identity is the Firebase uid (unverified JWT decode — cheap, since full verification already happens in `dependencies.get_current_user`) when a Bearer token is present, otherwise the client IP — so unauthenticated routes like `/health` still get limited.
- Wired `RateLimitMiddleware` into `backend/app/api/main.py`.
- Added `backend/requirements.txt` — didn't exist yet even for Phase 1/2's dependencies (`fastapi`, `firebase-admin`, `google-cloud-firestore`, etc. had only been installed ad hoc). Added it now plus Phase 3's new deps (`httpx`, `pyjwt`).
- Added `RATE_LIMIT_REQUESTS_PER_MINUTE` (optional, defaults to 30) to `.env.example`.
- `tests/phase3_redis_ratelimit_test.py` — end-to-end test using a fake in-memory Upstash REST server (`httpx.MockTransport`), so it needs no real Upstash account to run.

## What's now working (proof, not vibes)

Running `python tests/phase3_redis_ratelimit_test.py` with `RATE_LIMIT_REQUESTS_PER_MINUTE=3`:
```
Budget for this run: 3 requests / 60s
✅ First 3 requests all succeeded (200)
✅ Request 4 correctly got 429: {'detail': 'Rate limit exceeded: 3 requests per 60s. Try again later.'}
   Retry-After header: 59
✅ Further requests in the same window stay at 429
✅ After TTL expiry, the counter reset and the request succeeded again
```
Also confirmed directly that `_identify_caller()` keys by `user:{uid}` when a Bearer JWT is present and by `ip:{host}` when it isn't.

## What broke / what I couldn't finish

- No Upstash account exists yet (still unchecked in `STATUS.md`'s prerequisites), so this has only been verified against a fake in-memory stand-in for the REST API, not the genuine service. The command protocol matches Upstash's documented REST format, but hasn't been round-tripped against production Upstash.

## Decisions made (and why)

- Used `httpx` + Upstash's REST endpoint directly instead of `redis-py` — the phase brief explicitly says "Upstash REST client," and REST fits FastAPI's stateless request cycle better than a pooled TCP connection would here.
- Rate limiter identity uses an *unverified* JWT decode rather than calling `firebase_auth.verify_id_token` a second time — that full verification already happens in `get_current_user` for protected routes, so re-doing it in the middleware would double the Firebase round-trips for no benefit. A forged token just rate-limits the forger under a bogus bucket, which is harmless.
- Left `ch:{channel_id}:*` namespacing as TODO comments in both new files, per this phase's explicit instruction not to build it early.

## Next concrete step

Phase 4 — LangGraph, single hardcoded channel. Before fully trusting Phase 3 in anything beyond local dev, create the real Upstash database and re-run `tests/phase3_redis_ratelimit_test.py`'s logic against it (or a quick manual `curl` loop) with real credentials in `.env`.

## Checkboxes ticked this session

- [x] Phase 3: `backend/app/core/redis_client.py` — thin wrapper around Upstash REST client with `get`, `set`, `incr`, TTL support
- [x] Phase 3: Wire real rate limiting into `backend/app/api/middleware/rate_limit.py` using key prefix `rl:*` (Ch.11 table) and a 60-second TTL
- [x] Phase 3: Confirm the 429 response fires after the configured request budget is exceeded
- [x] Phase 3: Leave the namespacing (`ch:{channel_id}:*`) as a TODO comment — real multi-tenant namespacing happens in Phase 6, don't build it early
