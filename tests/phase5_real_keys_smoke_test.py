"""
Phase 5 — REAL KEYS smoke test.

Companion to tests/phase4_real_keys_smoke_test.py, same idea: unlike
tests/phase5_qdrant_rag_test.py (everything faked), this makes real
calls — Gemini generation, Gemini embeddings, Serper, Google Trends,
Upstash Redis, and a real Qdrant Cloud cluster.

Proves this phase's actual Definition of Done: "a research run returns
a summary that visibly cites retrieved chunks, and querying Qdrant
directly shows points landing in the correct collection with correct
metadata." The faked test proves the wiring; this proves it against the
real services.

Run with:
    python phase5_real_keys_smoke_test.py

Requires everything phase4_real_keys_smoke_test.py needs, plus:
    QDRANT_URL
    QDRANT_API_KEY
"""

import asyncio
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

REQUIRED_ENV_VARS = [
    "GEMINI_API_KEY",
    "GROQ_API_KEY",
    "SERPER_API_KEY",
    "UPSTASH_REDIS_REST_URL",
    "UPSTASH_REDIS_REST_TOKEN",
    "QDRANT_URL",
    "QDRANT_API_KEY",
]

missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
if missing:
    print(f"❌ Missing required .env values: {missing}")
    print("   Add them to .env at the repo root, then re-run this script.")
    sys.exit(1)

from app.core.qdrant_client import get_qdrant, channel_filter  # noqa: E402
from ai.rag.collections import ensure_collections, EMBEDDING_DIM  # noqa: E402
from ai.rag.embed import embed_text  # noqa: E402
from ai.langgraph.graph import get_graph  # noqa: E402
from ai.langgraph.hardcoded_channel import HARDCODED_CHANNEL  # noqa: E402


async def main():
    channel_id = HARDCODED_CHANNEL["channel_id"]

    # ── Step 1: real embedding call, in isolation ───────────────────────
    print("=== Step 1: real Gemini embedding call ===")
    vector = embed_text("test embedding for Phase 5 real-keys verification")
    print(f"✅ Got a real embedding vector, length={len(vector)} (expected {EMBEDDING_DIM})")
    if len(vector) != EMBEDDING_DIM:
        print(f"❌ MISMATCH: embed_text() returned {len(vector)} dims, EMBEDDING_DIM={EMBEDDING_DIM}")

    # ── Step 2: real Qdrant — create collections ────────────────────────
    print("\n=== Step 2: ensure_collections() against real Qdrant ===")
    created = ensure_collections()
    print(f"✅ ensure_collections() ran clean. Newly created this call: {created or '(none — already existed)'}")

    qdrant = get_qdrant()
    before_count = qdrant.count("research", query_filter=channel_filter(channel_id))
    print(f"   'research' collection currently has {before_count} point(s) for channel '{channel_id}'")

    # ── Step 3: real end-to-end pipeline run (exercises RAG retrieval + write-back) ──
    print("\n=== Step 3: real pipeline run (Trend -> Research w/ RAG -> ... -> Review) ===")
    graph = get_graph()
    initial_state = {
        "channel_id": channel_id,
        "parent_uid": "phase5_real_keys_smoke_test",
        "run_id": str(uuid.uuid4()),
        "channel_config": HARDCODED_CHANNEL,
    }
    final_state = await graph.ainvoke(initial_state)

    print("STATUS:", final_state.get("status"))
    print("REVIEW VERDICT:", final_state.get("review_verdict"))
    print("TOPIC:", final_state.get("topic"))
    summary = final_state.get("research_summary", "") or ""
    print("\nRESEARCH SUMMARY:\n", summary)

    cites_retrieved_chunk = "[Retrieved:" in summary
    print(
        ("✅" if cites_retrieved_chunk else "ℹ️ "),
        "Summary visibly cites a retrieved chunk"
        if cites_retrieved_chunk
        else "No '[Retrieved: ...]' citation this run — expected if this is the FIRST real run "
        "for this topic (nothing to retrieve yet). Run this script a second time on the same "
        "day to see a citation, since the first run's write-back gives the second run something "
        "to find.",
    )

    # ── Step 4: query Qdrant directly, confirm the write-back landed ───
    print("\n=== Step 4: querying Qdrant directly for the write-back ===")
    after_count = qdrant.count("research", query_filter=channel_filter(channel_id))
    print(f"'research' collection now has {after_count} point(s) for channel '{channel_id}' (was {before_count})")

    if after_count > before_count:
        print(f"✅ {after_count - before_count} new point(s) landed in 'research' after this run")
        # Pull one back to confirm metadata shape.
        query_vector = embed_text(final_state.get("topic", "test"), task_type="RETRIEVAL_QUERY")
        hits = qdrant.search(
            "research",
            vector=query_vector,
            limit=1,
            query_filter=channel_filter(channel_id),
        )
        if hits:
            payload = hits[0].get("payload", {})
            print("Sample point payload:", json.dumps(payload, indent=2))
            has_channel_id = payload.get("channel_id") == channel_id
            has_topic = bool(payload.get("topic"))
            print(("✅" if has_channel_id else "❌"), "payload.channel_id matches this channel")
            print(("✅" if has_topic else "❌"), "payload.topic is present")
    else:
        print("ℹ️  No new point count change — check whether this run hit the Redis research cache "
              "(a cache hit skips write-back entirely, by design).")

    print("\n" + "=" * 70)
    if final_state.get("status") == "reviewed":
        print("✅ Real Phase 5 end-to-end run completed successfully.")
    else:
        print(f"⚠️  Run ended with status='{final_state.get('status')}' — see above for details.")


if __name__ == "__main__":
    asyncio.run(main())
