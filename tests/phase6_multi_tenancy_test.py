"""
Phase 6 — Multi-Tenancy: Channel Brain, Workspace, Channel Factory test
script.

What this proves (per phases/phase-06-multi-tenancy-channel-factory/PHASE.md's
Definition of Done):
"Two different Firebase users can each create a channel, run the Phase 4
pipeline against their own channel independently, and neither can read,
list, or trigger the other's channel — verified by an automated test,
not manual inspection."

Concretely:
1. User A calls POST /workspaces (idempotent), POST /channels (through
   the real Channel Factory — fig 12d.1's chain), and
   POST /channels/{id}/generate — gets a real reviewed pipeline result
   back, same shape Phase 4 proved.
2. User B does the same, independently, with their own workspace and
   channel.
3. GET /channels for User A never includes User B's channel, and vice
   versa (the "list" guarantee).
4. User B's token requesting User A's channel's /generate is rejected
   with 403 — and, critically, LangGraph's graph.ainvoke is NEVER
   called for that request (the "trigger" guarantee, checked at the
   middleware/dependency layer, not just by the response code).
5. Every Redis key the factory and pipeline write is namespaced
   `ch:{channel_id}:*` (Ch.12b retrofit).
6. Provider keys submitted at channel creation are encrypted at rest —
   never stored as plaintext.

Everything external (Redis, Qdrant, Gemini, Groq, Serper/web search,
Firestore) is faked/mocked in-process — no real API keys, Firebase
project, or network access needed to run.

Run with:
    python phase6_multi_tenancy_test.py
"""

from __future__ import annotations

import asyncio
import math
import os
import re
import sys
import time

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

from cryptography.fernet import Fernet  # noqa: E402

os.environ.setdefault("CHANNEL_SECRETS_ENCRYPTION_KEY", Fernet.generate_key().decode())

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import httpx  # noqa: E402
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


# ── Fake in-memory Upstash REST server (same as Phase 3/4/5's tests) ───────
class FakeUpstash:
    def __init__(self):
        self._store: dict = {}
        self._expires_at: dict = {}

    def _expire_if_due(self, key):
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


# ── Fake in-memory Qdrant REST server (same as Phase 5's test) ─────────────
class FakeQdrant:
    def __init__(self):
        self.collections: dict[str, list[dict]] = {}

    def _matches(self, payload: dict, query_filter: dict | None) -> bool:
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
            # Real Qdrant requires an explicit payload index before filtering
            # on a field (caught for real against a live cluster — see
            # qdrant_client.py's create_payload_index docstring). The fake
            # doesn't need to enforce that requirement itself, just accept
            # the call so ensure_collection()'s index-creation step doesn't
            # fail here the way it would on an unhandled route.
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


# ── Fake embedding (bag-of-words, same trick as Phase 5's test) ────────────
_VOCAB = ["ai", "coding", "assistants", "adoption", "developers", "topic", "research"]


def fake_embed(text, model="gemini-embedding-001", task_type="RETRIEVAL_DOCUMENT", output_dimensionality=768):
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    vec = [float(tokens.count(w)) for w in _VOCAB]
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


from integrations.gemini import client as gemini_client_module  # noqa: E402

gemini_client_module.embed = fake_embed


# ── Fake in-memory Firestore ────────────────────────────────────────────────
class FakeSnapshot:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


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


# ── Fake LLM layer (same shape as Phase 4/5's tests) ────────────────────────
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


# ── Fake web search ──────────────────────────────────────────────────────
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


# ── Updated in Phase 7 ───────────────────────────────────────────────────
# POST /generate now enqueues a real Celery chain on a passing review
# (graph.py's new `enqueue_render` node) instead of the run just ending.
# This file cares about multi-tenant isolation and permission checks
# (Ch.12), not the render pipeline itself — that's
# tests/phase7_async_workers_test.py's job — so run Celery in eager mode
# with the four worker tasks' external calls faked, same doubles as
# Phase 7's own test and phase4_langgraph_test.py's Phase 7 update,
# rather than force this file to need a live Redis broker.
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
os.environ.setdefault("WORKER_OUTPUT_DIR", "/tmp/ai_carryon_phase6_test")
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
        f.write(b"fake-mp4-for-phase6-test")
    return _FakeCompletedProcess()


_voice_worker_module.generate_speech = lambda *a, **k: b"fake-mp3-for-phase6-test"
_render_worker_module.subprocess.run = _fake_ffmpeg_run
_upload_worker_module.upload_video = lambda **k: "fake_video_id_phase6_test"
_upload_worker_module._channel_youtube_token = lambda channel_id: None


# ── App setup: Firestore + auth faked, auth reads a per-request test header
# so different TestClient calls can act as different users ─────────────────
from app.api.main import app  # noqa: E402
from app.api.dependencies import get_current_user, get_firestore  # noqa: E402


from starlette.requests import Request  # noqa: E402


def fake_get_current_user(request: Request):
    uid = request.headers.get("X-Test-Uid", "anonymous")
    return {"uid": uid}


app.dependency_overrides[get_current_user] = fake_get_current_user
app.dependency_overrides[get_firestore] = lambda: fake_db

# Also patch the module directly, since some call sites (permissions.py,
# routers) resolve get_firestore via direct dependency injection that
# FastAPI's overrides cover, but any code calling init_firebase() at
# import time would still try to touch real Firebase — short-circuit that.
from app.api.middleware import auth as auth_module  # noqa: E402

auth_module._initialized = True

client = TestClient(app)


def headers_for(uid: str) -> dict:
    return {"Authorization": "Bearer fake", "X-Test-Uid": uid}


# ═══════════════════════════════════════════════════════════════════════════
# Test 1: User A — workspace, channel (via the real Factory), and a full run
# ═══════════════════════════════════════════════════════════════════════════
print("=== Test 1: User A creates a workspace, a channel, and runs the pipeline ===")

resp = client.post("/workspaces", headers=headers_for("user_a"))
check("POST /workspaces (User A) returns 200", resp.status_code == 200)
workspace_a = resp.json()
check("workspace has User A as a member", "user_a" in workspace_a.get("members", []))

resp_again = client.post("/workspaces", headers=headers_for("user_a"))
check(
    "POST /workspaces is idempotent (same workspace_id on second call)",
    resp_again.json().get("workspace_id") == workspace_a.get("workspace_id"),
)

channel_payload_a = {
    "name": "User A's Tech Channel",
    "category": "AI, coding, and future technology",
    "provider_keys": {"gemini_api_key": "user-a-super-secret-key"},
}
resp = client.post("/channels", json=channel_payload_a, headers=headers_for("user_a"))
check("POST /channels (User A) returns 200", resp.status_code == 200)
channel_a = resp.json()
channel_a_id = channel_a["channel_id"]
check("channel status is 'ready' after the Factory chain completes", channel_a.get("status") == "ready")
check("channel is attached to User A's workspace", channel_a.get("workspace_id") == workspace_a["workspace_id"])

# Factory step 3 (Create Redis Namespace): a marker key should exist,
# correctly namespaced ch:{channel_id}:*.
check(
    "factory wrote a ch:{channel_id}:* Redis namespace marker",
    f"ch:{channel_a_id}:_namespace_created_at" in fake_upstash.keys(),
)

# Provider key encryption: the stored value must not be the plaintext.
stored_keys = fake_db.collection("channel_provider_keys")._docs.get(channel_a_id, {})
check(
    "provider key was stored encrypted, not as plaintext",
    stored_keys.get("gemini_api_key") is not None and stored_keys["gemini_api_key"] != "user-a-super-secret-key",
)

resp = client.post(f"/channels/{channel_a_id}/generate", headers=headers_for("user_a"))
check("POST /channels/{id}/generate (User A, own channel) returns 200", resp.status_code == 200)
run_a = resp.json()
check("User A's run produced a script", bool(run_a.get("script")))
check("User A's run produced SEO", bool(run_a.get("seo")))
check("User A's run review_verdict is pass", run_a.get("review_verdict") == "pass")

# Every Redis key this run touched for this channel must be ch:{channel_id}:*-namespaced.
research_keys = [k for k in fake_upstash.keys() if "research" in k]
check(
    "research cache key is ch:{channel_id}:-namespaced",
    all(k.startswith(f"ch:{channel_a_id}:") for k in research_keys) and len(research_keys) > 0,
)


# ═══════════════════════════════════════════════════════════════════════════
# Test 2: User B — an independent workspace, channel, and run
# ═══════════════════════════════════════════════════════════════════════════
print("\n=== Test 2: User B independently creates their own workspace, channel, and run ===")

resp = client.post("/workspaces", headers=headers_for("user_b"))
workspace_b = resp.json()
check("User B's workspace is different from User A's", workspace_b["workspace_id"] != workspace_a["workspace_id"])

channel_payload_b = {"name": "User B's Cooking Channel", "category": "home cooking"}
resp = client.post("/channels", json=channel_payload_b, headers=headers_for("user_b"))
channel_b = resp.json()
channel_b_id = channel_b["channel_id"]
check("User B's channel is different from User A's", channel_b_id != channel_a_id)

resp = client.post(f"/channels/{channel_b_id}/generate", headers=headers_for("user_b"))
check("POST /channels/{id}/generate (User B, own channel) returns 200", resp.status_code == 200)


# ═══════════════════════════════════════════════════════════════════════════
# Test 3: neither user can list, read, or trigger the other's channel
# ═══════════════════════════════════════════════════════════════════════════
print("\n=== Test 3: Ch.12e isolation — list, and trigger, both ways ===")

list_a = client.get("/channels", headers=headers_for("user_a")).json()
list_b = client.get("/channels", headers=headers_for("user_b")).json()
check("User A's channel list never includes User B's channel", channel_b_id not in [c["channel_id"] for c in list_a])
check("User B's channel list never includes User A's channel", channel_a_id not in [c["channel_id"] for c in list_b])

# The critical negative test: patch get_graph so we can PROVE it's never
# invoked for a rejected cross-tenant request, not just check the status code.
#
# Updated in Phase 8: the actual `get_graph()` call moved out of
# app.api.routers.channels and into app.services.generation_service's
# `run_generation` (shared, as of Phase 8, with the new Scheduler-triggered
# route) — same reason this file's Phase 7 update note gives for touching
# other phases' tests: the code this test patches moved, the guarantee it
# proves did not.
import app.services.generation_service as generation_service_module  # noqa: E402

graph_invocations = {"count": 0}
real_get_graph = generation_service_module.get_graph


class _TripwireGraph:
    async def ainvoke(self, state):
        graph_invocations["count"] += 1
        raise AssertionError("graph.ainvoke was called for a request that should have been rejected earlier")


generation_service_module.get_graph = lambda: _TripwireGraph()

resp = client.post(f"/channels/{channel_a_id}/generate", headers=headers_for("user_b"))
check("User B requesting User A's channel gets 403", resp.status_code == 403)
check("graph.ainvoke was never called for the rejected request", graph_invocations["count"] == 0)

resp = client.post(f"/channels/{channel_b_id}/generate", headers=headers_for("user_a"))
check("User A requesting User B's channel gets 403 (symmetric)", resp.status_code == 403)
check("graph.ainvoke still never called", graph_invocations["count"] == 0)

generation_service_module.get_graph = real_get_graph  # restore for any later use

resp = client.post("/channels/does_not_exist/generate", headers=headers_for("user_a"))
check("requesting a channel that doesn't exist at all gets 404, not 403", resp.status_code == 404)


# ═══════════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}\n{passed} passed, {failed} failed\n{'=' * 60}")
if failed:
    sys.exit(1)
