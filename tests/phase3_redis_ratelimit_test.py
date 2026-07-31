"""
Phase 3 — Redis (Upstash) rate limiter test script.

What this proves (per BUILD_GUIDE.md Phase 3 Definition of Done):
1. Hammering /health past the configured per-minute budget returns 429.
2. Waiting past the 60s TTL resets the counter and requests succeed again.

This runs entirely in-process against a fake in-memory Upstash REST
server (via httpx.MockTransport) so it needs no real Upstash account —
useful for local iteration. Point UPSTASH_REDIS_REST_URL /
UPSTASH_REDIS_REST_TOKEN at a real Upstash database and delete the
monkeypatch block below to run it against the genuine service instead.

Run with:
    python phase3_redis_ratelimit_test.py
"""

import os
import sys
import time

os.environ.setdefault("UPSTASH_REDIS_REST_URL", "https://fake-upstash.example.com")
os.environ.setdefault("UPSTASH_REDIS_REST_TOKEN", "fake-token")
os.environ["RATE_LIMIT_REQUESTS_PER_MINUTE"] = "3"  # low budget so the test is fast

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import httpx
from fastapi.testclient import TestClient


# ── Fake in-memory Upstash REST server ──────────────────────────────────────
class FakeUpstash:
    """Implements just enough of Upstash's REST command protocol (POST /
    with a JSON command array, returns {"result": ...}) for GET/SET/INCR/
    EXPIRE/TTL, backed by a plain dict with real wall-clock TTL expiry.
    """

    def __init__(self):
        self._store: dict[str, str] = {}
        self._expires_at: dict[str, float] = {}

    def _expire_if_due(self, key: str) -> None:
        exp = self._expires_at.get(key)
        if exp is not None and time.time() >= exp:
            self._store.pop(key, None)
            self._expires_at.pop(key, None)

    def handle(self, request: httpx.Request) -> httpx.Response:
        import json

        command = json.loads(request.content)
        op = command[0].upper()

        if op == "GET":
            key = command[1]
            self._expire_if_due(key)
            return httpx.Response(200, json={"result": self._store.get(key)})

        if op == "SET":
            key, value = command[1], command[2]
            self._store[key] = value
            if len(command) >= 5 and command[3].upper() == "EX":
                self._expires_at[key] = time.time() + int(command[4])
            else:
                self._expires_at.pop(key, None)
            return httpx.Response(200, json={"result": "OK"})

        if op == "INCR":
            key = command[1]
            self._expire_if_due(key)
            new_value = int(self._store.get(key, "0")) + 1
            self._store[key] = str(new_value)
            return httpx.Response(200, json={"result": new_value})

        if op == "EXPIRE":
            key, seconds = command[1], int(command[2])
            self._expires_at[key] = time.time() + seconds
            return httpx.Response(200, json={"result": 1})

        if op == "TTL":
            key = command[1]
            self._expire_if_due(key)
            if key not in self._store:
                return httpx.Response(200, json={"result": -2})
            exp = self._expires_at.get(key)
            if exp is None:
                return httpx.Response(200, json={"result": -1})
            return httpx.Response(200, json={"result": max(0, int(exp - time.time()))})

        if op == "DEL":
            key = command[1]
            self._store.pop(key, None)
            self._expires_at.pop(key, None)
            return httpx.Response(200, json={"result": 1})

        return httpx.Response(400, json={"error": f"unsupported op {op}"})


fake_upstash = FakeUpstash()

from app.core import redis_client as redis_client_module  # noqa: E402

_real_client = redis_client_module.RedisClient()
_real_client._client = httpx.Client(
    base_url=_real_client._base_url,
    transport=httpx.MockTransport(fake_upstash.handle),
)
redis_client_module._platform_client = _real_client

from app.api.main import app  # noqa: E402  (import after monkeypatch so it uses the fake)

client = TestClient(app)

# ── 1. Requests within budget should all succeed ────────────────────────────
budget = int(os.environ["RATE_LIMIT_REQUESTS_PER_MINUTE"])
print(f"Budget for this run: {budget} requests / 60s")

ok_count = 0
for i in range(budget):
    resp = client.get("/health")
    if resp.status_code == 200:
        ok_count += 1
    else:
        print(f"❌ FAILED: request {i + 1} within budget got {resp.status_code}, expected 200")

if ok_count == budget:
    print(f"✅ First {budget} requests all succeeded (200)")
else:
    print(f"❌ FAILED: only {ok_count}/{budget} succeeded within budget")

# ── 2. The next request should be rejected with 429 ─────────────────────────
resp = client.get("/health")
if resp.status_code == 429:
    print(f"✅ Request {budget + 1} correctly got 429: {resp.json()}")
    print(f"   Retry-After header: {resp.headers.get('retry-after')}")
else:
    print(f"❌ FAILED: expected 429, got {resp.status_code}: {resp.text}")

# A few more should also be 429 while the window is still open.
still_limited = all(client.get("/health").status_code == 429 for _ in range(3))
if still_limited:
    print("✅ Further requests in the same window stay at 429")
else:
    print("❌ FAILED: a request inside the still-active window was not limited")

# ── 3. Simulate the TTL expiring, then confirm the window resets ───────────
# (Fast-forward the fake store's clock instead of sleeping 60s for real.)
key = "rl:ip:testclient"
if key in fake_upstash._expires_at:
    fake_upstash._expires_at[key] = time.time() - 1  # force-expire
else:
    print(f"⚠️  Expected key {key!r} not found in fake store — check the identity keying logic")

resp = client.get("/health")
if resp.status_code == 200:
    print("✅ After TTL expiry, the counter reset and the request succeeded again")
else:
    print(f"❌ FAILED: expected 200 after TTL reset, got {resp.status_code}: {resp.text}")

print("\n🎉 Phase 3 test script finished.")
