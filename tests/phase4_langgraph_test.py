"""
Phase 4 — LangGraph core agents test script.

What this proves (per phases/phase-04-langgraph-core-agents/PHASE.md's
Definition of Done):
1. A full run produces a reviewed script + SEO + thumbnail brief for the
   hardcoded "AI carryON" channel.
2. A forced Review failure demonstrably retries the correct single
   agent — not all six.

Everything external (Redis, Gemini, Serper/web search, Google Trends) is
faked/mocked in-process, so this needs no real API keys or network
access to run — useful for fast local iteration and for CI. It does NOT
prove your real Gemini/Groq/Serper keys work end-to-end; see
phase4_real_keys_smoke_test.py (or the handoff notes) for that.

Updated in Phase 6: Test 1 originally drove this through
POST /channels/ai_carryon/generate over HTTP. Phase 6 legitimately
changed that route to multi-tenant routing (Ch.12b/12e) — there's no
hardcoded single-channel HTTP shortcut anymore, by design — so Test 1
now calls the LangGraph engine directly instead, the way Test 2 always
has. tests/phase6_multi_tenancy_test.py re-proves this same happy path
through the *current* HTTP endpoint, plus the isolation guarantees this
file never had reason to check.

Run with:
    python phase4_langgraph_test.py
"""

import asyncio
import os
import sys
import time

os.environ.setdefault("UPSTASH_REDIS_REST_URL", "https://fake-upstash.example.com")
os.environ.setdefault("UPSTASH_REDIS_REST_TOKEN", "fake-token")
os.environ.setdefault("GEMINI_API_KEY", "fake-gemini-key")
os.environ.setdefault("GROQ_API_KEY", "fake-groq-key")
os.environ.setdefault("SERPER_API_KEY", "fake-serper-key")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# ── Updated in Phase 7 ───────────────────────────────────────────────────
# A passing review now enqueues a real Celery chain (graph.py's new
# `enqueue_render` terminal node) instead of the run just ending. This
# file cares about the review/retry logic (Ch.04/Ch.08), not the render
# pipeline itself — that's tests/phase7_async_workers_test.py's job — so
# run Celery in eager mode with the four worker tasks' external calls
# faked, the same doubles Phase 7's own test uses, rather than force
# this file to need a live Redis broker just to reach its happy path.
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
os.environ.setdefault("WORKER_OUTPUT_DIR", "/tmp/ai_carryon_phase4_test")
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
        f.write(b"fake-mp4-for-phase4-test")
    return _FakeCompletedProcess()


_voice_worker_module.generate_speech = lambda *a, **k: b"fake-mp3-for-phase4-test"
_render_worker_module.subprocess.run = _fake_ffmpeg_run
_upload_worker_module.upload_video = lambda **k: "fake_video_id_phase4_test"
_upload_worker_module._channel_youtube_token = lambda channel_id: None

import httpx

# ── Fake in-memory Upstash REST server (same as Phase 3's test) ────────────
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


fake_upstash = FakeUpstash()

from app.core import redis_client as redis_client_module  # noqa: E402

_fake_redis = redis_client_module.RedisClient()
_fake_redis._client = httpx.Client(
    base_url=_fake_redis._base_url,
    transport=httpx.MockTransport(fake_upstash.handle),
)
redis_client_module._client = _fake_redis


# ── Fake LLM layer ───────────────────────────────────────────────────────────
# Detects which agent is calling based on the "You are the X Agent" opening
# line of its system prompt (see prompt_library.py), and counts REAL calls
# per agent so the retry test can assert only one agent's count moves.
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
            '"audience": "developers", "branding": {"channel_id": "ai_carryon", "logo_position": "bottom_right"}}'
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
        return '["ai", "coding", "developer tools", "llm", "programming", "tech news", "ai carryon"]'
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


# ── Fake web search ──────────────────────────────────────────────────────────
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


# ── Test 1: happy path — the LangGraph pipeline itself ─────────────────────
# Originally this called POST /channels/ai_carryon/generate over HTTP.
# Phase 6 legitimately changed that route's behavior (multi-tenant routing
# through the Channel Factory/Permission Check, Ch.12b/12e) — a hardcoded
# single-channel HTTP shortcut no longer exists, by design, and Phase 6's
# own test (tests/phase6_multi_tenancy_test.py) re-proves this exact happy
# path through the *current* HTTP endpoint, plus the isolation guarantees
# Phase 4 never had to worry about. What THIS test still needs to prove —
# and still can, unchanged — is that the LangGraph engine itself (the
# actual Trend -> Research -> Planner -> Parallel(6) -> Review pipeline)
# produces a correct result, so it now calls the graph directly, the same
# way Test 2 below always has, instead of through HTTP.
print("=== Test 1: full pipeline happy path via the LangGraph engine directly ===")

from ai.langgraph.graph import get_graph  # noqa: E402
from ai.langgraph.hardcoded_channel import HARDCODED_CHANNEL  # noqa: E402
import uuid  # noqa: E402


async def run_happy_path():
    graph = get_graph()
    initial_state = {
        "channel_id": HARDCODED_CHANNEL["channel_id"],
        "parent_uid": "test_uid",
        "run_id": str(uuid.uuid4()),
        "channel_config": HARDCODED_CHANNEL,
    }
    return await graph.ainvoke(initial_state)


body = asyncio.run(run_happy_path())
checks = [
    ("status == reviewed", body.get("status") == "reviewed"),
    ("review_verdict == pass", body.get("review_verdict") == "pass"),
    ("script present", bool(body.get("script"))),
    ("seo present", bool(body.get("seo"))),
    ("thumbnail_brief present", bool(body.get("thumbnail_brief"))),
    ("hook present", bool(body.get("hook"))),
    ("tags present", bool(body.get("tags"))),
    ("description present", bool(body.get("description"))),
]
all_ok = True
for label, ok in checks:
    print(("✅" if ok else "❌"), label)
    all_ok = all_ok and ok
if all_ok:
    print("✅ Test 1 PASSED — full run produced a reviewed script + SEO + thumbnail brief")
else:
    print("❌ Test 1 FAILED")


# ── Test 2: forced Review failure retries only the correct single agent ────
print("\n=== Test 2: forced Review failure retries exactly one agent ===")
real_call_counts.clear()

FORCE_FAIL_TARGET = "seo"

async def run_forced_failure():
    graph = get_graph()
    initial_state = {
        "channel_id": HARDCODED_CHANNEL["channel_id"],
        "parent_uid": "test_uid",
        "run_id": str(uuid.uuid4()),
        "channel_config": HARDCODED_CHANNEL,
        "force_fail_agent": FORCE_FAIL_TARGET,
    }
    return await graph.ainvoke(initial_state)

final_state = asyncio.run(run_forced_failure())

print("Real LLM call counts per agent:", real_call_counts)

writer_agent_labels = {
    "script": "Script Agent",
    "seo": "SEO Agent",
    "thumbnail": "Thumbnail Agent",
    "hook": "Hook Agent",
    "tags": "Tags Agent",
    "description": "Description Agent",
}

ok = True
final_verdict_ok = final_state.get("review_verdict") == "pass"
print(("✅" if final_verdict_ok else "❌"), f"Run eventually reached review_verdict == pass (got {final_state.get('review_verdict')})")
ok = ok and final_verdict_ok

for agent_key, label in writer_agent_labels.items():
    expected = 2 if agent_key == FORCE_FAIL_TARGET else 1
    actual = real_call_counts.get(label, 0)
    check_ok = actual == expected
    print(
        ("✅" if check_ok else "❌"),
        f"{agent_key}: expected {expected} real call(s), got {actual}",
    )
    ok = ok and check_ok

if ok:
    print(f"✅ Test 2 PASSED — only '{FORCE_FAIL_TARGET}' re-ran; the other five writers ran exactly once each")
else:
    print("❌ Test 2 FAILED")

print("\n🎉 Phase 4 test script finished.")
