# Work Report — 2026-07-25

**Phase worked on:** Phase 5 follow-up — real-keys verification
**Author:** Claude
**Time spent:** ~1.5 hrs (mostly Qdrant Cloud signup/setup guidance, plus three debugging rounds on one bug)

## What happened

The repo owner created a real Qdrant Cloud cluster (closing the last piece needed for full real-key verification across Phases 3-5) and ran `tests/phase5_real_keys_smoke_test.py`.

## Bug #1: retired embedding model (caught proactively, before a real run)

Before recommending the real test, checked Google's deprecation table (prompted by Phase 4's earlier retired-`gemini-1.5-flash` bug) and found `gemini-embedding-001` — Phase 5's default embedding model — had an official shutdown date of July 14, 2026, eleven days before this was checked. Switched to `gemini-embedding-2` before the repo owner spent a test run hitting the same wall Phase 4 hit. This one was caught proactively, not by a failure.

## Bug #2: real Qdrant requires an explicit payload index (three attempts)

First real run: embedding call succeeded (768-dim, confirming the Bug #1 fix was correct), `ensure_collections()` reported success, but the very next call — counting points filtered by `channel_id` — failed with a real `400`: `"Index required but not found for \"channel_id\"..."`. Real Qdrant Cloud requires an explicit payload index before filtering on a field; the faked test server never enforced this, so it had no way to catch it.

**Attempt 1:** added `create_payload_index()`, called from `ensure_collection()`. Reported success. **Didn't fix it** — identical error on the next real run.

**Attempt 2:** reasoned that Qdrant processes index creation asynchronously by default, so the very next query could be racing ahead of it finishing. Added `wait=true`, matching the precedent already in `upsert()`. Well-reasoned, matched Qdrant's documented behavior. **Still didn't fix it** — identical error again.

**Attempt 3, actual root cause:** fetched `/collections/research` directly and saw `"payload_schema":{}` — completely empty, even after two "fixes." That meant the code containing both fixes wasn't running at all. Traced it to `ai/rag/collections.py`'s `ensure_collections()`, which had its own `if not client.collection_exists(name)` check *before* ever calling `client.ensure_collection()`. Since all nine collections already existed (from the very first real run, before any fix shipped), that outer check was `False` for every single one — so `ensure_collection()`, and therefore both attempted fixes inside it, never executed at all. Removed the redundant pre-check; `ensure_collection()` now always runs (with its own internal existence check just for collection *creation*, separate from the index) and returns whether it created a new collection, so the caller can still track that.

**Confirmed fixed** on the next real run: the `count()` call that had failed three times in a row succeeded cleanly.

## Full success, with one expected wrinkle explained correctly

The first full pipeline run after the fix hit the Redis research cache from an earlier Phase 4 test run (same topic, same day, 24h TTL) and correctly skipped RAG retrieval/write-back — the test script's own output correctly explained this as expected cache behavior rather than reporting a false failure. Deleted that one cache key, re-ran: real web search, real RAG retrieval, real LLM summarization, and a real point landed in Qdrant's `research` collection with correct `channel_id`/`topic` metadata.

Independently fact-checked the resulting research summary's claims (same practice as Phase 4's verification): "Nano Banana" (genuinely real, well-documented Google DeepMind model family — has its own Wikipedia page), Gemini 3.6 Flash, GPT-5.6 Luna/Sol, Claude Opus 5, Grok 4.5, Kimi K3 all checked out as accurate. Second real run in a row where every claim held up.

## Decisions made (and why)

- **Verify fixes are actually being reached, not just logically correct** — the `wait=true` fix in attempt 2 was reasoned correctly from Qdrant's real documented behavior, and still didn't work, because the code containing it wasn't executing at all. The lesson (now written into the handoff notes): when an identical error persists after a well-reasoned fix, check whether the fixed code path is reachable before assuming the reasoning itself was wrong.
- **Said so plainly when a fix hadn't been re-verified yet**, rather than assuming success — this caught attempt 2's failure quickly instead of it sitting undiscovered.

## Next concrete step

Phase 5 is now fully closed out — real-verified across every piece except `backfill.py` (low priority, no real old-pipeline export exists to test it against) and directly observing a `[Retrieved: ...]` citation on a real run (the write-back mechanics are confirmed; only the retrieval-and-cite half on a real embedding wasn't directly observed this session). Phase 6 — Multi-Tenancy — is next per `STATUS.md`.
