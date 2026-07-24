"""
Phase 4 — REAL KEYS smoke test.

Unlike tests/phase4_langgraph_test.py (which fakes every external call so
it can run anywhere with no keys and no network), this script makes real
calls to Gemini, Serper, Google Trends, and Upstash Redis using whatever
credentials are in your .env file. Costs a small, real amount of API
usage each run (a handful of Gemini calls + one Serper search) — cheap on
free tiers, but not free-free, so don't loop this in a script.

This deliberately bypasses the FastAPI endpoint (and therefore Firebase
auth) and calls the compiled LangGraph graph directly — the fastest way
to eyeball real output quality without needing a real Firebase ID token.
POST /channels/ai_carryon/generate exercises the exact same graph once
you have a real auth token to test the HTTP layer too.

Run with:
    python phase4_real_keys_smoke_test.py

Requires .env to have real values for:
    GEMINI_API_KEY
    GROQ_API_KEY       (only used if Gemini falls back — see DEFAULT_FALLBACK_CHAIN)
    SERPER_API_KEY
    UPSTASH_REDIS_REST_URL
    UPSTASH_REDIS_REST_TOKEN
"""

import asyncio
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv

# Load .env from the repo root regardless of what directory this is run from.
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

REQUIRED_ENV_VARS = [
    "GEMINI_API_KEY",
    "SERPER_API_KEY",
    "UPSTASH_REDIS_REST_URL",
    "UPSTASH_REDIS_REST_TOKEN",
]

missing = [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]
if missing:
    print(f"❌ Missing required .env values: {missing}")
    print("   Add them to .env at the repo root, then re-run this script.")
    sys.exit(1)

from ai.langgraph.graph import get_graph  # noqa: E402
from ai.langgraph.hardcoded_channel import HARDCODED_CHANNEL  # noqa: E402


async def main():
    print("Running the real pipeline for channel:", HARDCODED_CHANNEL["channel_id"])
    print("(This makes real Gemini + Serper + Google Trends + Upstash calls — a few seconds.)\n")

    graph = get_graph()
    initial_state = {
        "channel_id": HARDCODED_CHANNEL["channel_id"],
        "parent_uid": "real_keys_smoke_test",
        "run_id": str(uuid.uuid4()),
        "channel_config": HARDCODED_CHANNEL,
    }

    final_state = await graph.ainvoke(initial_state)

    print("=" * 70)
    print("STATUS:", final_state.get("status"))
    print("REVIEW VERDICT:", final_state.get("review_verdict"))
    print("TOPIC:", final_state.get("topic"))
    print("TREND CANDIDATES:", final_state.get("trend_candidates"))
    print("=" * 70)
    print("\nRESEARCH SUMMARY:\n", final_state.get("research_summary"))
    print("\nRESEARCH SOURCES:\n", final_state.get("research_sources"))
    print("\nPLANNER JSON:\n", json.dumps(final_state.get("planner_json"), indent=2))
    print("\nSCRIPT:\n", final_state.get("script"))
    print("\nSEO:\n", json.dumps(final_state.get("seo"), indent=2))
    print("\nTHUMBNAIL BRIEF:\n", json.dumps(final_state.get("thumbnail_brief"), indent=2))
    print("\nHOOK:\n", final_state.get("hook"))
    print("\nTAGS:\n", final_state.get("tags"))
    print("\nDESCRIPTION:\n", final_state.get("description"))
    print("\nREVIEW FINDINGS:\n", json.dumps(final_state.get("review_findings"), indent=2))
    if final_state.get("failure_reason"):
        print("\nFAILURE REASON:\n", final_state.get("failure_reason"))
    print("\n" + "=" * 70)

    if final_state.get("status") == "reviewed":
        print("✅ Real end-to-end run completed and passed Review.")
        print("   Read the script/SEO/thumbnail output above for QUALITY, not just shape —")
        print("   that's the part no automated test can judge for you.")
    else:
        print(f"⚠️  Run ended with status='{final_state.get('status')}' — see FAILURE REASON above.")


if __name__ == "__main__":
    asyncio.run(main())
