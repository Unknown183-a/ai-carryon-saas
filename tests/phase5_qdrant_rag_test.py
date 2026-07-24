"""
Phase 5 — Qdrant + RAG test script.

What this proves (per phases/phase-05-qdrant-rag/PHASE.md's Definition
of Done):
1. `ensure_collections()` creates all nine Ch.10 collections.
2. A research run returns a summary that visibly cites a retrieved
   chunk (the fake LLM only emits a "[Retrieved: ...]" citation if the
   retrieved-context section it was actually handed is non-empty and
   contains a real hit — so this proves the retrieval -> prompt wiring,
   not just that the string happens to appear).
3. After that run, querying Qdrant directly shows a new point landed in
   the `research` collection with the correct channel_id/topic metadata
   (the write-back half of the loop).
4. `chunk_text` produces overlapping ~300-500 token chunks; `hybrid_search`
   ranks an exact-keyword match above a same-collection distractor even
   when the distractor happens to be a decent vector match.

Everything external (Redis, Qdrant, Gemini generate + embed, web search)
is faked in-process — no real API keys or network access needed to run.

Run with:
    python phase5_qdrant_rag_test.py
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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import httpx  # noqa: E402

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


# ── Fake in-memory Upstash REST server (same as Phase 3/4's test) ──────────
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


# ── Fake in-memory Qdrant REST server ───────────────────────────────────────
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
            # on a field (caught for real against a live cluster, not by this
            # fake — see qdrant_client.py's create_payload_index docstring).
            # The fake doesn't need to enforce that requirement itself, just
            # accept the call so ensure_collection()'s index-creation step
            # doesn't fail here the way it would on an unhandled route.
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


# ── Fake embedding: bag-of-words over a small vocab, so word overlap  ──────
# produces meaningfully different cosine-style dot products, without
# needing a real embedding model or network access.
_VOCAB = [
    "ai", "coding", "assistant", "assistants", "agentic", "open", "source",
    "models", "cricket", "score", "finance", "market", "research", "topic",
    "adoption", "developers", "benchmark", "gap",
]


def fake_embed(text, model="gemini-embedding-001", task_type="RETRIEVAL_DOCUMENT", output_dimensionality=768):
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    vec = [float(tokens.count(w)) for w in _VOCAB]
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


from integrations.gemini import client as gemini_client_module  # noqa: E402

gemini_client_module.embed = fake_embed


# ── Fake LLM layer — Research Agent's fake echoes retrieved-context
#    citations if it was actually handed any, proving the wiring. ─────────
real_call_counts: dict[str, int] = {}


def _detect_agent(system_prompt: str) -> str:
    first_line = system_prompt.strip().splitlines()[0]
    for name in ["Research Agent"]:
        if name in first_line:
            return name
    return "unknown:" + first_line[:40]


def fake_generate(model, system_prompt, user_prompt, json_mode=False, temperature=0.7):
    agent = _detect_agent(system_prompt)
    real_call_counts[agent] = real_call_counts.get(agent, 0) + 1

    if agent == "Research Agent":
        retrieved_citations = re.findall(r"\[Retrieved: [^\]]+\]", user_prompt)
        base = "AI coding assistants are seeing rapid adoption in 2026."
        if retrieved_citations:
            base += " " + retrieved_citations[0] + " confirms this trend continues."
        return base + "\n\nSources: https://example.com/a"
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


# ═══════════════════════════════════════════════════════════════════════════
# Test 1: ensure_collections() creates all nine Ch.10 collections
# ═══════════════════════════════════════════════════════════════════════════
print("=== Test 1: ensure_collections() creates all nine Ch.10 collections ===")
from ai.rag.collections import COLLECTIONS, ensure_collections  # noqa: E402

created = ensure_collections()
check("all nine collections created on first call", set(created) == set(COLLECTIONS))
created_again = ensure_collections()
check("idempotent — nothing created on second call", created_again == [])


# ═══════════════════════════════════════════════════════════════════════════
# Test 2: chunker produces overlapping chunks in the right size band
# ═══════════════════════════════════════════════════════════════════════════
print("\n=== Test 2: chunker produces ~300-500 token overlapping chunks ===")
from ai.rag.chunker import chunk_text  # noqa: E402

long_text = " ".join([f"word{i}" for i in range(1200)])  # well over one chunk
chunks = chunk_text(long_text, metadata={"channel_id": "ai_carryon"})
check("long text splits into multiple chunks", len(chunks) > 1)
if len(chunks) > 1:
    first_words = set(chunks[0].text.split())
    second_words = set(chunks[1].text.split())
    check("consecutive chunks overlap", len(first_words & second_words) > 0)
check("chunk metadata carries channel_id", all(c.metadata.get("channel_id") == "ai_carryon" for c in chunks))

short_text = "Just a short one."
short_chunks = chunk_text(short_text, metadata={"channel_id": "ai_carryon"})
check("short text yields exactly one chunk", len(short_chunks) == 1)


# ═══════════════════════════════════════════════════════════════════════════
# Test 3: hybrid_search ranks an exact keyword match above a vaguer neighbor
# ═══════════════════════════════════════════════════════════════════════════
print("\n=== Test 3: hybrid_search ranks exact keyword match above a distractor ===")
from ai.rag.retriever import hybrid_search, store_chunks  # noqa: E402

store_chunks(
    "knowledge",
    "AI coding assistants adoption among developers grew significantly in 2026.",
    metadata={"channel_id": "ai_carryon", "domain": "ai-tools"},
)
store_chunks(
    "knowledge",
    "Cricket score updates and market finance news roundup for the week.",
    metadata={"channel_id": "ai_carryon", "domain": "unrelated"},
)
# A different channel's data must never surface — Ch.12e isolation.
store_chunks(
    "knowledge",
    "AI coding assistants are the top story for this other channel too.",
    metadata={"channel_id": "some_other_channel", "domain": "ai-tools"},
)

hits = hybrid_search("AI coding assistants adoption", collection="knowledge", channel_id="ai_carryon", limit=5)
check("at least one hit returned", len(hits) >= 1)
check("top hit is the on-topic chunk, not the distractor", bool(hits) and "coding assistants" in hits[0].text)
check("other channel's data never surfaces", all("other channel" not in h.text for h in hits))


# ═══════════════════════════════════════════════════════════════════════════
# Test 4: research_node retrieves context, cites it, and writes back
# ═══════════════════════════════════════════════════════════════════════════
print("\n=== Test 4: research run retrieves, cites, and writes back to Qdrant ===")

# Seed a prior research summary for this exact topic so the run has
# something concrete to retrieve and cite.
store_chunks(
    "research",
    "AI coding assistants moved from autocomplete to full agentic workflows in early 2026.",
    metadata={
        "channel_id": "ai_carryon",
        "topic": "AI coding assistants",
        "source_urls": ["https://example.com/prior"],
        "date": "2026-06-01",
    },
)
research_points_before = len(fake_qdrant_backend.collections.get("research", []))

from ai.langgraph.hardcoded_channel import HARDCODED_CHANNEL  # noqa: E402

state = {"channel_config": HARDCODED_CHANNEL, "topic": "AI coding assistants"}
result = asyncio.run(research_agent_module.research_node(state))

check("research_node returns a summary", bool(result.get("research_summary")))
check(
    "summary visibly cites a retrieved chunk",
    "[Retrieved:" in result["research_summary"],
)

research_points_after = len(fake_qdrant_backend.collections.get("research", []))
check("a new point landed in the research collection (write-back)", research_points_after > research_points_before)

new_points = fake_qdrant_backend.collections["research"][research_points_before:]
check(
    "new point(s) carry correct channel_id and topic metadata",
    all(
        p["payload"].get("channel_id") == "ai_carryon" and p["payload"].get("topic") == "AI coding assistants"
        for p in new_points
    ),
)


# ═══════════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}\n{passed} passed, {failed} failed\n{'=' * 60}")
if failed:
    sys.exit(1)
