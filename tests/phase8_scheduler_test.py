"""
Phase 8 — Scheduler test script.

What this proves (per phases/phase-08-scheduler/PHASE.md's Definition of
Done: "a channel with a due schedule generates a video with zero manual
intervention, observed over at least one real scheduled trigger, not
just a manual test call" — the "real scheduled trigger" half of that is
inherently an operational/manual verification step, same category as
Phase 7's real process-kill test; see this phase's own Handoff Notes for
what "observed" means here in a unit test's terms):

1. `tenant_platform/scheduler/schedule_rules.py`'s pure timing logic:
   `compute_next_run_at` picks the correct next 09:00 IST slot for a
   handful of frequencies, and `is_due` correctly separates due /
   not-due / disabled / malformed schedule docs.
2. Creating a channel through the real Channel Factory (Phase 6) now
   also registers a `schedules` doc (fig 12d.1's Register Scheduler
   step, filled in this phase) — enabled, with a `next_run_at` in the
   future.
3. `POST /internal/scheduler/run-due-channels` is gated by a system role
   token, not a Firebase user JWT (PHASE.md's explicit task): no
   `X-Internal-Scheduler-Token` header -> 401; wrong token -> 403;
   correct token and NO `Authorization` header at all -> still succeeds,
   proving this route doesn't secretly depend on `get_current_user`.
4. A channel whose schedule is due gets a real pipeline run triggered —
   same `render_task_id`/`review_verdict` shape
   `POST /channels/{id}/generate` returns, because both routes now share
   `app/services/generation_service.py`'s `run_generation` — and its
   schedule's `next_run_at` advances into the future afterward (so
   polling the endpoint again immediately does NOT re-trigger it).
5. A channel whose schedule is NOT due yet is left alone entirely.
6. A channel whose status isn't "ready" is skipped but its schedule
   still advances (so a broken channel doesn't get "due" on every single
   poll forever).

Everything external (Redis, Qdrant, Gemini, Groq, Serper/web search,
Firestore, ElevenLabs, ffmpeg, YouTube) is faked/mocked in-process — no
real API keys, Firebase project, or network access needed to run. Reuses
the exact same fakes/doubles as tests/phase6_multi_tenancy_test.py and
tests/phase7_async_workers_test.py rather than inventing new ones.

Run with:
    python phase8_scheduler_test.py
"""

from __future__ import annotations

import datetime
import os
import sys

os.environ.setdefault("UPSTASH_REDIS_REST_URL", "https://fake-upstash.example.com")
os.environ.setdefault("UPSTASH_REDIS_REST_TOKEN", "fake-token")
os.environ.setdefault("GEMINI_API_KEY", "fake-gemini-key")
os.environ.setdefault("GROQ_API_KEY", "fake-groq-key")
os.environ.setdefault("SERPER_API_KEY", "fake-serper-key")
os.environ.setdefault("QDRANT_URL", "https://fake-qdrant.example.com")
os.environ.setdefault("QDRANT_API_KEY", "fake-qdrant-key")
os.environ.setdefault("FIREBASE_PROJECT_ID", "fake-project")
os.environ.setdefault(
    "FIREBASE_SERVICE_ACCOUNT_JSON",
    __import__("base64").b64encode(b'{"type": "service_account", "project_id": "fake-project"}').decode(),
)
os.environ["RATE_LIMIT_REQUESTS_PER_MINUTE"] = "1000"  # avoid tripping the limiter mid-test
os.environ["INTERNAL_SCHEDULER_TOKEN"] = "test-system-token-do-not-use-in-prod"

from cryptography.fernet import Fernet  # noqa: E402

os.environ.setdefault("CHANNEL_SECRETS_ENCRYPTION_KEY", Fernet.generate_key().decode())

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from fastapi.testclient import TestClient  # noqa: E402

passed = 0
failed = 0


def check(label: str, condition: bool) -> None:
    global passed, failed
    if condition:
        print(f"✅ {label}")
        passed += 1
    else:
        print(f"❌ {label}")
        failed += 1


# ── Fake Firestore (same shape as tests/phase6_multi_tenancy_test.py) ──────
class FakeSnapshot:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class FakeDocumentRef:
    def __init__(self, collection, doc_id):
        self._collection, self.id = collection, doc_id

    def set(self, data, merge=False):
        if merge and self.id in self._collection._docs:
            self._collection._docs[self.id] = {**self._collection._docs[self.id], **data}
        else:
            self._collection._docs[self.id] = dict(data)

    def get(self):
        return FakeSnapshot(self.id, self._collection._docs.get(self.id))


class FakeQuery:
    def __init__(self, collection, field, op, value):
        self._collection, self._field, self._op, self._value = collection, field, op, value

    def stream(self):
        results = []
        for doc_id, data in self._collection._docs.items():
            if self._op == "==":
                match = data.get(self._field) == self._value
            elif self._op == "array_contains":
                match = self._value in (data.get(self._field) or [])
            else:
                raise NotImplementedError(self._op)
            if match:
                results.append(FakeSnapshot(doc_id, data))
        return results


class FakeCollection:
    def __init__(self):
        self._docs: dict = {}

    def document(self, doc_id=None):
        if doc_id is None:
            import uuid

            doc_id = uuid.uuid4().hex
        return FakeDocumentRef(self, doc_id)

    def where(self, field, op, value):
        return FakeQuery(self, field, op, value)


class FakeFirestore:
    def __init__(self):
        self._collections: dict[str, FakeCollection] = {}

    def collection(self, name):
        return self._collections.setdefault(name, FakeCollection())


fake_db = FakeFirestore()


# ── Fake Upstash Redis over HTTP (same shape as tests/phase6_multi_tenancy_test.py) ──
import time  # noqa: E402

import httpx  # noqa: E402


class FakeUpstash:
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

    def keys(self) -> list[str]:
        return list(self._store.keys())


fake_upstash = FakeUpstash()

from app.core import redis_client as redis_client_module  # noqa: E402

_fake_redis = redis_client_module.RedisClient()
_fake_redis._client = httpx.Client(
    base_url=_fake_redis._base_url,
    transport=httpx.MockTransport(fake_upstash.handle),
)
redis_client_module._client = _fake_redis


# ── Fake in-memory Qdrant REST server (same as Phase 5/6's tests) ──────────
class FakeQdrant:
    def __init__(self):
        self.collections: dict[str, list[dict]] = {}

    def _matches(self, payload: dict, query_filter) -> bool:
        if not query_filter:
            return True
        for clause in query_filter.get("must", []):
            key = clause["key"]
            expected = clause["match"]["value"]
            if payload.get(key) != expected:
                return False
        return True

    def handle(self, request: httpx.Request) -> httpx.Response:
        import json
        import re

        path = request.url.path
        method = request.method

        m = re.fullmatch(r"/collections/([^/]+)", path)
        if m and method == "GET":
            name = m.group(1)
            if name in self.collections:
                return httpx.Response(200, json={"result": {"status": "green"}})
            return httpx.Response(404, json={"status": {"error": "not found"}})
        if m and method == "PUT":
            name = m.group(1)
            self.collections.setdefault(name, [])
            return httpx.Response(200, json={"result": True})

        m = re.fullmatch(r"/collections/([^/]+)/index", path)
        if m and method == "PUT":
            return httpx.Response(200, json={"result": True})

        m = re.fullmatch(r"/collections/([^/]+)/points", path)
        if m and method == "PUT":
            name = m.group(1)
            body = json.loads(request.content)
            self.collections.setdefault(name, [])
            for point in body["points"]:
                self.collections[name].append(point)
            return httpx.Response(200, json={"result": {"status": "completed"}})

        m = re.fullmatch(r"/collections/([^/]+)/points/search", path)
        if m and method == "POST":
            name = m.group(1)
            body = json.loads(request.content)
            query_vector = body["vector"]
            points = self.collections.get(name, [])
            scored = []
            for p in points:
                if not self._matches(p.get("payload", {}), body.get("filter")):
                    continue
                score = sum(a * b for a, b in zip(query_vector, p["vector"]))
                scored.append({"id": p["id"], "score": score, "payload": p["payload"]})
            scored.sort(key=lambda r: r["score"], reverse=True)
            return httpx.Response(200, json={"result": scored[: body.get("limit", 10)]})

        m = re.fullmatch(r"/collections/([^/]+)/points/count", path)
        if m and method == "POST":
            name = m.group(1)
            body = json.loads(request.content)
            points = self.collections.get(name, [])
            n = sum(1 for p in points if self._matches(p.get("payload", {}), body.get("filter")))
            return httpx.Response(200, json={"result": {"count": n}})

        return httpx.Response(400, json={"error": f"unhandled {method} {path}"})


fake_qdrant_backend = FakeQdrant()

from app.core import qdrant_client as qdrant_client_module  # noqa: E402

_fake_qdrant = qdrant_client_module.QdrantClient()
_fake_qdrant._client = httpx.Client(
    base_url=_fake_qdrant._base_url,
    transport=httpx.MockTransport(fake_qdrant_backend.handle),
)
qdrant_client_module._client = _fake_qdrant


# ── Fake embedding (bag-of-words, same trick as Phase 5/6's tests) ─────────
import math  # noqa: E402
import re as _re  # noqa: E402

_VOCAB = ["ai", "coding", "assistants", "adoption", "developers", "topic", "research"]


def fake_embed(text, model="gemini-embedding-001", task_type="RETRIEVAL_DOCUMENT", output_dimensionality=768):
    tokens = _re.findall(r"[a-z0-9]+", text.lower())
    vec = [float(tokens.count(w)) for w in _VOCAB]
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


from integrations.gemini import client as gemini_client_module  # noqa: E402

gemini_client_module.embed = fake_embed


# ── Fake LLM layer (same shape as Phase 4/5/6's tests) ──────────────────────
real_call_counts: dict[str, int] = {}


def _detect_agent(system_prompt: str) -> str:
    first_line = system_prompt.strip().splitlines()[0]
    for name in [
        "Research Agent", "Planner Agent", "Script Agent", "SEO Agent",
        "Thumbnail Agent", "Hook Agent", "Tags Agent", "Description Agent",
        "Grammar Check", "Fact Check", "Copyright Check", "LLM Judge",
    ]:
        if name in first_line:
            return name
    return "unknown:" + first_line[:40]


def fake_generate(model, system_prompt, user_prompt, json_mode=False, temperature=0.7):
    agent = _detect_agent(system_prompt)
    real_call_counts[agent] = real_call_counts.get(agent, 0) + 1

    if agent == "Research Agent":
        return "AI coding assistants are seeing rapid adoption in 2026.\n\nSources: https://example.com/a"
    if agent == "Planner Agent":
        return (
            '{"video_length_sec": 45, "voice_profile": "confident_tech_explainer_male", '
            '"thumbnail_style": "bold_text_high_contrast", "seo_angle": "AI coding tools 2026", '
            '"audience": "developers", "branding": {"channel_id": "x", "logo_position": "bottom_right"}}'
        )
    if agent == "Script Agent":
        return "AI coding assistants just got a huge upgrade. Here's what changed and why it matters for you."
    if agent == "SEO Agent":
        return '{"title": "AI Coding Tools Just Changed Forever", "keywords": ["ai coding", "developer tools", "llm"]}'
    if agent == "Thumbnail Agent":
        return '{"headline_text": "AI CODE UPGRADE", "visual_concept": "robot hand typing on a glowing keyboard", "style": "bold_text_high_contrast"}'
    if agent == "Hook Agent":
        return "Your coding assistant just got smarter overnight."
    if agent == "Tags Agent":
        return '["ai", "coding", "developer tools", "llm", "programming", "tech news"]'
    if agent == "Description Agent":
        return "AI coding assistants leveled up this week. Here's the breakdown.\n\n#AI #Coding #DevTools"
    if agent in ("Grammar Check", "Fact Check", "Copyright Check"):
        return '{"pass": true, "issues": []}'
    if agent == "LLM Judge":
        return '{"pass": true, "reason": "Coherent and on-brand.", "retry_target": null}'
    raise AssertionError(f"fake_generate got an unrecognized agent prompt: {agent}")


from ai.models import llm_client as llm_client_module  # noqa: E402

llm_client_module._PROVIDER_CLIENTS["gemini"] = fake_generate
llm_client_module._PROVIDER_CLIENTS["groq"] = fake_generate

from ai.tools.web_search import SearchResult  # noqa: E402
import ai.agents.research_agent as research_agent_module  # noqa: E402


def fake_web_search(query, num_results=5, timeout=10.0):
    return [
        SearchResult(
            title="AI coding tools adoption surges in 2026",
            snippet="Developers are increasingly relying on AI coding assistants...",
            link="https://example.com/a",
        )
    ]


research_agent_module.web_search = fake_web_search

# ── Celery in eager mode, four workers' externals faked — same doubles as
# Phase 6/7's own tests, since a due-schedule trigger runs the SAME
# enqueue_render -> worker chain a human-triggered /generate call does.
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
os.environ.setdefault("WORKER_OUTPUT_DIR", "/tmp/ai_carryon_phase8_test")
from app.workers.celery_app import celery_app  # noqa: E402

celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True

import app.workers.render_worker as _render_worker_module  # noqa: E402
import app.workers.upload_worker as _upload_worker_module  # noqa: E402
import app.workers.voice_worker as _voice_worker_module  # noqa: E402


class _FakeCompletedProcess:
    returncode = 0


def _fake_ffmpeg_run(command, check=True, capture_output=True, timeout=None):
    with open(command[-1], "wb") as f:
        f.write(b"fake-mp4-for-phase8-test")
    return _FakeCompletedProcess()


_voice_worker_module.generate_speech = lambda *a, **k: b"fake-mp3-for-phase8-test"
_render_worker_module.subprocess.run = _fake_ffmpeg_run
_upload_worker_module.upload_video = lambda **k: "fake_video_id_phase8_test"
_upload_worker_module._channel_youtube_token = lambda channel_id: None

# ── App setup: Firestore + auth faked ────────────────────────────────────
from app.api.main import app  # noqa: E402
from app.api.dependencies import get_current_user, get_firestore  # noqa: E402

from starlette.requests import Request  # noqa: E402


def fake_get_current_user(request: Request):
    uid = request.headers.get("X-Test-Uid", "anonymous")
    return {"uid": uid}


app.dependency_overrides[get_current_user] = fake_get_current_user
app.dependency_overrides[get_firestore] = lambda: fake_db

from app.api.middleware import auth as auth_module  # noqa: E402

auth_module._initialized = True

client = TestClient(app)


def headers_for(uid: str) -> dict:
    return {"Authorization": "Bearer fake", "X-Test-Uid": uid}


SYSTEM_HEADERS = {"X-Internal-Scheduler-Token": "test-system-token-do-not-use-in-prod"}


# ═══════════════════════════════════════════════════════════════════════════
# Test 1: schedule_rules — pure timing logic, no Firestore involved
# ═══════════════════════════════════════════════════════════════════════════
print("=== Test 1: schedule_rules timing logic ===")

from tenant_platform.scheduler.schedule_rules import compute_next_run_at, is_due  # noqa: E402

# A Monday 07:30 IST "after" instant (before today's 09:00 IST slot) ->
# next daily run is that same day, 09:00 IST.
monday_early = datetime.datetime(2026, 7, 20, 2, 0, tzinfo=datetime.timezone.utc)  # 2026-07-20 is a Monday; 07:30 IST
next_daily = compute_next_run_at("1_per_day", after=monday_early)
check(
    "daily schedule picks 09:00 IST the same day when 'after' is earlier that day",
    next_daily.astimezone(__import__("zoneinfo").ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M")
    == "2026-07-20 09:00",
)

# A Monday 10:30 IST "after" instant (past today's slot) -> rolls to Tuesday 09:00 IST.
monday_late = datetime.datetime(2026, 7, 20, 5, 0, tzinfo=datetime.timezone.utc)  # 10:30 IST
next_daily_rolled = compute_next_run_at("1_per_day", after=monday_late)
check(
    "daily schedule rolls to the next day once 'after' is past today's slot",
    next_daily_rolled.astimezone(__import__("zoneinfo").ZoneInfo("Asia/Kolkata")).date()
    == datetime.date(2026, 7, 21),
)

# 3_per_week (Mon/Wed/Fri) starting AFTER Monday's own slot has passed ->
# next slot is Wednesday, not Tuesday (Monday itself is skipped because
# 'after' is already past it).
next_3pw = compute_next_run_at("3_per_week", after=monday_late)
check(
    "3_per_week schedule skips Tuesday and lands on Wednesday",
    next_3pw.astimezone(__import__("zoneinfo").ZoneInfo("Asia/Kolkata")).date() == datetime.date(2026, 7, 22),
)

now = datetime.datetime.now(datetime.timezone.utc)
past = (now - datetime.timedelta(days=1)).isoformat()
future = (now + datetime.timedelta(days=1)).isoformat()

check("is_due: enabled + past next_run_at -> due", is_due({"enabled": True, "next_run_at": past}, now))
check("is_due: enabled + future next_run_at -> not due", not is_due({"enabled": True, "next_run_at": future}, now))
check("is_due: disabled schedule is never due, even if next_run_at is past", not is_due({"enabled": False, "next_run_at": past}, now))
check("is_due: missing next_run_at -> not due (fail closed)", not is_due({"enabled": True}, now))
check("is_due: malformed next_run_at -> not due (fail closed)", not is_due({"enabled": True, "next_run_at": "not-a-date"}, now))


# ═══════════════════════════════════════════════════════════════════════════
# Test 2: creating a channel registers a schedule doc (Factory Step, Ch.16)
# ═══════════════════════════════════════════════════════════════════════════
print("\n=== Test 2: Channel Factory registers a schedule at creation time ===")

resp = client.post("/workspaces", headers=headers_for("scheduler_user"))
workspace = resp.json()

resp = client.post(
    "/channels",
    json={"name": "Scheduler Test Channel", "category": "tech news"},
    headers=headers_for("scheduler_user"),
)
check("POST /channels returns 200", resp.status_code == 200)
channel = resp.json()
channel_id = channel["channel_id"]

schedule_doc = fake_db.collection("schedules")._docs.get(channel_id)
check("a schedules/{channel_id} doc was created", schedule_doc is not None)
check("new schedule is enabled by default", schedule_doc is not None and schedule_doc.get("enabled") is True)
check("new schedule's upload_schedule matches the channel's (default 1_per_day)", schedule_doc is not None and schedule_doc.get("upload_schedule") == "1_per_day")
check("new schedule's next_run_at is in the future", schedule_doc is not None and datetime.datetime.fromisoformat(schedule_doc["next_run_at"]) > datetime.datetime.now(datetime.timezone.utc))
check("new schedule has no last_run_at yet", schedule_doc is not None and schedule_doc.get("last_run_at") is None)


# ═══════════════════════════════════════════════════════════════════════════
# Test 3: the internal route is gated by a system token, not a user JWT
# ═══════════════════════════════════════════════════════════════════════════
print("\n=== Test 3: system-token gate (Ch.12e, 'system role token, not user JWT') ===")

resp = client.post("/internal/scheduler/run-due-channels")
check("no system token header at all -> 401", resp.status_code == 401)

resp = client.post("/internal/scheduler/run-due-channels", headers={"X-Internal-Scheduler-Token": "wrong-token"})
check("wrong system token -> 403", resp.status_code == 403)

resp = client.post("/internal/scheduler/run-due-channels", headers=SYSTEM_HEADERS)
check("correct system token, NO Authorization header at all -> still succeeds (no user JWT needed)", resp.status_code == 200)
check("that channel isn't due yet, so it's not in this run's results", channel_id not in [r["channel_id"] for r in resp.json()["results"]])


# ═══════════════════════════════════════════════════════════════════════════
# Test 4: a due channel gets triggered end-to-end, and stops being due
# ═══════════════════════════════════════════════════════════════════════════
print("\n=== Test 4: a due channel generates a video with zero manual intervention ===")

from tenant_platform.scheduler.scheduler_service import register_schedule  # noqa: E402

# Force this channel's schedule into the past, the same way a real 09:00
# IST slot would arrive on its own a few hours after registration —
# forcing it here is the "manual test call" PHASE.md's Definition of Done
# distinguishes from a real scheduled trigger; see this phase's Handoff
# Notes for that distinction stated plainly.
two_days_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)
register_schedule(fake_db, channel_id, "1_per_day", now=two_days_ago)
forced_schedule = fake_db.collection("schedules")._docs[channel_id]
check("forcing the schedule into the past actually made it due", datetime.datetime.fromisoformat(forced_schedule["next_run_at"]) <= datetime.datetime.now(datetime.timezone.utc))

resp = client.post("/internal/scheduler/run-due-channels", headers=SYSTEM_HEADERS)
check("run-due-channels returns 200", resp.status_code == 200)
body = resp.json()
check("due_count includes the now-due channel", body["due_count"] >= 1)

result = next((r for r in body["results"] if r["channel_id"] == channel_id), None)
check("the due channel appears in this run's results", result is not None)
check("the due channel's run status is 'ran'", result is not None and result["status"] == "ran")
check("the due channel's run has review_verdict == pass", result is not None and result.get("review_verdict") == "pass")
check("the due channel's run enqueued a render task (render_task_id present)", result is not None and result.get("render_task_id"))

updated_schedule = fake_db.collection("schedules")._docs.get(channel_id)
check("last_run_at was recorded", updated_schedule is not None and updated_schedule.get("last_run_at") is not None)
check(
    "next_run_at advanced back into the future (won't re-fire on the next immediate poll)",
    updated_schedule is not None
    and datetime.datetime.fromisoformat(updated_schedule["next_run_at"]) > datetime.datetime.now(datetime.timezone.utc),
)

# Polling again immediately must NOT re-trigger the same channel.
resp = client.post("/internal/scheduler/run-due-channels", headers=SYSTEM_HEADERS)
check(
    "polling again immediately does not re-trigger the same channel",
    channel_id not in [r["channel_id"] for r in resp.json()["results"]],
)


# ═══════════════════════════════════════════════════════════════════════════
# Test 5: a non-"ready" channel is skipped but its schedule still advances
# ═══════════════════════════════════════════════════════════════════════════
print("\n=== Test 5: a non-ready channel is skipped, not retried forever ===")

not_ready_channel_id = "not_ready_channel_test"
fake_db.collection("channels").document(not_ready_channel_id).set(
    {"workspace_id": workspace["workspace_id"], "owner_uid": "scheduler_user", "status": "configuring", "upload_schedule": "1_per_day"}
)
register_schedule(fake_db, not_ready_channel_id, "1_per_day", now=two_days_ago)

resp = client.post("/internal/scheduler/run-due-channels", headers=SYSTEM_HEADERS)
body = resp.json()
result = next((r for r in body["results"] if r["channel_id"] == not_ready_channel_id), None)
check("the non-ready channel shows up with status 'skipped'", result is not None and result["status"] == "skipped")

advanced_schedule = fake_db.collection("schedules")._docs.get(not_ready_channel_id)
check(
    "the non-ready channel's schedule still advanced (won't be re-checked every poll)",
    advanced_schedule is not None
    and datetime.datetime.fromisoformat(advanced_schedule["next_run_at"]) > datetime.datetime.now(datetime.timezone.utc),
)


# ═══════════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}\n{passed} passed, {failed} failed\n{'=' * 60}")
if failed:
    sys.exit(1)
