"""
Phase 10 — Monitoring & Alerts test script.

What this proves (per phases/phase-10-monitoring-alerts/PHASE.md's
Definition of Done): simulating Redis going down results in an alert
reaching an inbox within the polling interval — end to end, through the
real health_agent.py LangGraph graph and the real alert_agent.py
retry-then-escalate policy, against fakes for every external service
(same convention as tests/phase3_redis_ratelimit_test.py's FakeUpstash
and tests/phase6_multi_tenancy_test.py's FakeFirestore — this file
builds its own small versions of both rather than importing phase6's,
since that module runs a full unrelated test suite at import time).

Also exercises: all 7 health checks passing (the "everything's fine"
case), and the retry-then-escalate table's actual counting behavior
directly (retry twice, escalate once, don't re-escalate on a 4th
failure) — not just the Redis-down scenario the Definition of Done
specifically calls out.

Run with:
    python tests/phase10_monitoring_test.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

os.environ.setdefault("UPSTASH_REDIS_REST_URL", "https://fake-upstash.example.com")
os.environ.setdefault("UPSTASH_REDIS_REST_TOKEN", "fake-token")
os.environ.setdefault("QDRANT_URL", "https://fake-qdrant.example.com")
os.environ.setdefault("QDRANT_API_KEY", "fake-token")
os.environ.setdefault("GEMINI_API_KEY", "fake")
os.environ.setdefault("GROQ_API_KEY", "fake")
os.environ.setdefault("OPENAI_API_KEY", "fake")
os.environ.setdefault("ALERT_EMAIL_TO", "ops@example.com")
os.environ.setdefault("ALERT_EMAIL_FROM", "alerts@example.com")
os.environ.setdefault("RESEND_API_KEY", "fake-resend-key")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import httpx  # noqa: E402

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"✅ {label}")
    else:
        print(f"❌ FAILED: {label} {detail}")
        failures.append(label)


# ── Fake in-memory Upstash REST server (same protocol as phase3's) ──────────
class FakeUpstash:
    def __init__(self):
        self._store: dict[str, str] = {}
        self._expires_at: dict[str, float] = {}
        self.down = False  # flip True to simulate Redis being unreachable

    def _expire_if_due(self, key: str) -> None:
        exp = self._expires_at.get(key)
        if exp is not None and time.time() >= exp:
            self._store.pop(key, None)
            self._expires_at.pop(key, None)

    def handle(self, request: httpx.Request) -> httpx.Response:
        import json

        if self.down:
            raise httpx.ConnectError("simulated Redis outage")

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
        if op == "DEL":
            key = command[1]
            self._store.pop(key, None)
            self._expires_at.pop(key, None)
            return httpx.Response(200, json={"result": 1})
        return httpx.Response(400, json={"error": f"unsupported op {op}"})


fake_upstash = FakeUpstash()

from app.core import redis_client as redis_client_module  # noqa: E402

_real_redis_client = redis_client_module.RedisClient()
_real_redis_client._client = httpx.Client(
    base_url=_real_redis_client._base_url,
    transport=httpx.MockTransport(fake_upstash.handle),
)
redis_client_module._client = _real_redis_client


# ── Fake Firestore (same shape as phase6's, plus .limit() support) ──────────
class FakeSnapshot:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data) if self._data else {}


class FakeDocumentRef:
    def __init__(self, collection, doc_id):
        self._collection = collection
        self.id = doc_id

    def set(self, data, merge=False):
        existing = self._collection._docs.get(self.id)
        if merge and existing is not None:
            merged = dict(existing)
            merged.update(data)
            self._collection._docs[self.id] = merged
        else:
            self._collection._docs[self.id] = dict(data)

    def get(self):
        return FakeSnapshot(self.id, self._collection._docs.get(self.id))


class FakeQuery:
    def __init__(self, collection, field=None, op=None, value=None):
        self._collection, self._field, self._op, self._value = collection, field, op, value
        self._limit = None

    def where(self, field, op, value):
        return FakeQuery(self._collection, field, op, value)

    def limit(self, n):
        self._limit = n
        return self

    def stream(self):
        results = []
        for doc_id, data in self._collection._docs.items():
            if self._field is None:
                match = True
            elif self._op == "==":
                match = data.get(self._field) == self._value
            else:
                raise NotImplementedError(self._op)
            if match:
                results.append(FakeSnapshot(doc_id, data))
        return results[: self._limit] if self._limit is not None else results


class FakeCollection:
    def __init__(self):
        self._docs: dict = {}

    def document(self, doc_id=None):
        if doc_id is None:
            import uuid

            doc_id = uuid.uuid4().hex
        return FakeDocumentRef(self, doc_id)

    def where(self, field, op, value):
        return FakeQuery(self).where(field, op, value)

    def limit(self, n):
        return FakeQuery(self).limit(n)


class FakeFirestore:
    def __init__(self):
        self._collections: dict[str, FakeCollection] = {}

    def collection(self, name):
        return self._collections.setdefault(name, FakeCollection())


fake_db = FakeFirestore()


# ── Fake Qdrant, Celery, YouTube ─────────────────────────────────────────────
class FakeQdrant:
    def __init__(self):
        self.up = True

    def collection_exists(self, name):
        if not self.up:
            raise ConnectionError("simulated Qdrant outage")
        return True


fake_qdrant = FakeQdrant()

from app.core import qdrant_client as qdrant_client_module  # noqa: E402

qdrant_client_module.get_qdrant = lambda: fake_qdrant

import types  # noqa: E402

fake_celery_module = types.ModuleType("app.workers.celery_app")


class _FakeInspect:
    def ping(self):
        return {"worker1@host": "pong"}


class _FakeControl:
    def inspect(self, timeout=5.0):
        return _FakeInspect()


class _FakeCeleryApp:
    control = _FakeControl()


fake_celery_module.celery_app = _FakeCeleryApp()
sys.modules["app.workers.celery_app"] = fake_celery_module

from integrations.youtube import client as youtube_client_module  # noqa: E402

youtube_client_module.check_connection = lambda token_json=None: {
    "ok": True,
    "detail": "fake channels.list succeeded",
    "quota_exceeded": False,
}

sent_emails: list[dict] = []

from integrations.resend import client as resend_client_module  # noqa: E402


def _fake_send_alert_email(to, subject, html_body, timeout=15.0):
    sent_emails.append({"to": to, "subject": subject, "html_body": html_body})
    return {"id": "fake-email-id"}


resend_client_module.send_alert_email = _fake_send_alert_email

# alert_agent.py imported `send_alert_email` by name at module scope, so
# it needs its own reference patched too, not just the source module's.
from tenant_platform.monitoring import alert_agent  # noqa: E402

alert_agent.send_alert_email = _fake_send_alert_email

from tenant_platform.monitoring import health_agent  # noqa: E402

# ── 1. Everything healthy ────────────────────────────────────────────────
print("--- Scenario 1: everything healthy ---")
result = asyncio.run(health_agent.run_health_check(fake_db))
check("overall_ok is True when all 7 checks pass", result["overall_ok"] is True)
check("all 7 services reported", len(result["services"]) == 7, f"got {len(result['services'])}")
for service in result["services"]:
    check(f"  {service['service']} reports ok=True", service["ok"] is True, service["detail"])

# ── 2. Alert Agent's retry-then-escalate table, directly ────────────────────
print("\n--- Scenario 2: retry-then-escalate counting (render_failure, max_retries=2) ---")
# Every real channel has a schedule doc from the moment it's created
# (Phase 8's Channel Factory hook) — create one here so
# set_schedule_enabled's pause action below has something to act on,
# same as it would for a real channel.
fake_db.collection("schedules").document("channel_abc").set({"channel_id": "channel_abc", "enabled": True})

actions = [
    alert_agent.record_failure(fake_db, "channel_abc", "render_failure", "ffmpeg crashed", workspace_id="ws1")
    for _ in range(4)
]
check("attempt 1 retries", actions[0]["action"] == "retry")
check("attempt 2 retries", actions[1]["action"] == "retry")
check("attempt 3 escalates", actions[2]["action"] == "escalated")
check("attempt 4 does not re-escalate", actions[3]["action"] == "already_escalated")
check("exactly one incident report created", len(fake_db.collection("incidents")._docs) == 1)
check("exactly one notification created", len(fake_db.collection("notifications")._docs) == 1)
check("exactly one email sent for this incident", len(sent_emails) == 1)
schedule_doc = fake_db.collection("schedules")._docs.get("channel_abc")
check("serious failure paused the channel's schedule", schedule_doc is not None and schedule_doc.get("enabled") is False)

# ── 3. Definition of Done: simulated Redis outage reaches an "inbox" ────────
print("\n--- Scenario 3: Redis outage -> alert reaches inbox within polling interval ---")
sent_emails.clear()
fake_upstash.down = True

poll_1 = asyncio.run(health_agent.run_health_check(fake_db))
redis_check_1 = next(s for s in poll_1["services"] if s["service"] == "redis")
check("poll 1: redis check reports ok=False during outage", redis_check_1["ok"] is False)
other_checks_1 = [s for s in poll_1["services"] if s["service"] != "redis"]
check("poll 1: the other 6 checks still succeed despite Redis being down", all(s["ok"] for s in other_checks_1))

actions_1 = alert_agent.handle_health_check_result(fake_db, poll_1)
redis_action_1 = next(a for a in actions_1 if a["failure_mode"] == "health:redis")
# record_failure can't track a retry count via Redis when Redis itself
# is what's unreachable — it escalates on the very first poll rather
# than silently crashing or, worse, waiting on a retry budget it has no
# way to count against. Faster than the retry-then-escalate table's
# normal behavior, and that's the right trade-off for this one case.
check("poll 1: escalates immediately (can't retry-count via Redis when Redis is the outage)", redis_action_1["action"] == "escalated")
check("poll 1: exactly one alert email sent", len(sent_emails) == 1)
if sent_emails:
    check("poll 1: email addressed to ALERT_EMAIL_TO", sent_emails[0]["to"] == os.environ["ALERT_EMAIL_TO"])
    check("poll 1: email subject mentions the failure", "health:redis" in sent_emails[0]["subject"])

poll_2 = asyncio.run(health_agent.run_health_check(fake_db))
actions_2 = alert_agent.handle_health_check_result(fake_db, poll_2)
redis_action_2 = next(a for a in actions_2 if a["failure_mode"] == "health:redis")
check("poll 2: does not send a duplicate email (in-process dedup)", redis_action_2["action"] == "already_escalated")
check("poll 2: still exactly one email sent total", len(sent_emails) == 1)

fake_upstash.down = False

# ── Summary ───────────────────────────────────────────────────────────────
print()
if failures:
    print(f"❌ {len(failures)} check(s) failed: {failures}")
    sys.exit(1)
print("✅ All Phase 10 checks passed.")
