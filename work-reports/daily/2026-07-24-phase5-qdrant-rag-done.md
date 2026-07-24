# Work Report — 2026-07-24

**Phase worked on:** Phase 5 — Qdrant + RAG
**Author:** Claude
**Time spent:** ~2 hrs

## What I built / did

- `backend/integrations/gemini/client.py` — added `embed()`, Gemini's `embed_content` wrapper (`gemini-embedding-001`, truncated to 768 dims, task-type aware for document vs. query embedding).
- `backend/app/core/qdrant_client.py` — thin REST wrapper for Qdrant (same "raw httpx, no SDK" pattern `redis_client.py` already established), with `channel_filter()` for the mandatory Ch.12e isolation filter.
- `backend/ai/rag/collections.py` — registry of all nine Ch.10 collections + `ensure_collections()`, idempotent, wired into FastAPI's startup event in `app/api/main.py` (swallows failures so an unreachable/unconfigured Qdrant doesn't block the API from starting).
- `backend/ai/rag/chunker.py` — word-count-approximated 300–500 token chunker with overlap (no tokenizer dependency added — documented approximation instead).
- `backend/ai/rag/embed.py` — `embed_text()`/`embed_batch()`, Redis-cached (`embed:*`, 7-day TTL per Ch.11), retried per Ch.05's policy.
- `backend/ai/rag/retriever.py` — `hybrid_search()` (vector similarity + keyword-overlap re-ranking, always channel-filtered) and `store_chunks()` (the write side: chunk → embed → upsert).
- `backend/ai/memory/channel_memory.py` — `get_lessons_learned()`, the first retrieval call that folder's README was waiting on.
- `backend/ai/agents/research_agent.py` — rewired per fig 5.1: retrieves from `research`+`knowledge` collections alongside web search, both feed the LLM, prompt asks for `[Retrieved: ...]` citations, and the fresh summary gets chunked/embedded/written back into `research` afterward.
- `backend/ai/prompts/prompt_library.py` — updated `research_summarizer_prompt()` to describe and require citing retrieved context.
- `backend/ai/rag/backfill.py` + `backend/ai/rag/seed_data/sample_backfill.json` — backfill script reading a JSON export into `scripts`/`research`, with an illustrative 5-entry sample.
- `tests/phase5_qdrant_rag_test.py` — full test suite, everything external faked (fake Qdrant does real cosine-style scoring + metadata filtering, fake embeddings are bag-of-words over a small vocab so similarity behaves meaningfully).

## What's now working (proof, not vibes)

Running `python tests/phase5_qdrant_rag_test.py`:
```
=== Test 1: ensure_collections() creates all nine Ch.10 collections ===
✅ all nine collections created on first call
✅ idempotent — nothing created on second call

=== Test 2: chunker produces ~300-500 token overlapping chunks ===
✅ long text splits into multiple chunks
✅ consecutive chunks overlap
✅ chunk metadata carries channel_id
✅ short text yields exactly one chunk

=== Test 3: hybrid_search ranks exact keyword match above a distractor ===
✅ at least one hit returned
✅ top hit is the on-topic chunk, not the distractor
✅ other channel's data never surfaces

=== Test 4: research run retrieves, cites, and writes back to Qdrant ===
✅ research_node returns a summary
✅ summary visibly cites a retrieved chunk
✅ a new point landed in the research collection (write-back)
✅ new point(s) carry correct channel_id and topic metadata

13 passed, 0 failed
```

Also re-ran `tests/phase4_langgraph_test.py` afterward — still passes unchanged (both tests), which incidentally proves the graceful-degradation path for real: that test never fakes Qdrant at all, so every retrieval/write-back call in this session's `research_agent.py` was hitting a real (fake-hostname) connection failure the whole time and quietly no-op'ing instead of failing the run.

Also directly verified (outside the test suite) that FastAPI's new startup hook doesn't crash the app when `QDRANT_URL` points at an unreachable host — logs a warning and continues.

## What broke / what I couldn't finish

Nothing broke — first full test run passed all 13 checks with no fixes needed. What's *not* verified (documented in the PHASE.md handoff, same honesty bar Phase 4 set): the real Gemini `embed_content` response shape, a real Qdrant Cloud cluster, and the backfill script against real old-pipeline data rather than the illustrative sample — this sandbox can't reach `generativelanguage.googleapis.com` or a real Qdrant Cloud instance (network egress is allow-listed to package registries and GitHub only).

## Decisions made (and why)

- **Raw REST wrapper over the `qdrant-client` SDK** — matches this codebase's one existing pattern for external stateful services (Upstash, Serper), and stays trivially fakeable with `httpx.MockTransport` the same way everything else here already is. No new dependency added.
- **`gemini-embedding-001` truncated to 768 dims** (not the 3072 default) — cheaper Qdrant storage/search, official Matryoshka-supported truncation, minimal quality loss. This is now a load-bearing constant shared between `integrations/gemini/client.py` and `ai/rag/collections.py`'s `EMBEDDING_DIM`.
- **Web search AND RAG, not RAG instead of web search** — fig 5.1 in the SAD shows both feeding the LLM; Phase 4's research agent used web-search-only as an explicit stand-in "per this brief," not a permanent design, so Phase 5 adds RAG alongside it rather than replacing it.
- **Retrieval and write-back are both best-effort (swallowed exceptions)** — a Qdrant outage should degrade the Research Agent, not fail the whole pipeline (Ch.16's Health Agent table says exactly this: "Qdrant down → Research Agent falls back to web search only").
- **Backfill reads a JSON export, not the old pipeline's SQLite DB directly** — that old pipeline lives in a different, inaccessible-from-here repo. Documented as a known gap rather than faked as done.

## Next concrete step

Begin Phase 6 (`phases/phase-06-multi-tenancy-channel-factory/PHASE.md`). Before then, or early in that phase, worth spending 15 minutes creating the real Qdrant Cloud cluster and Upstash account (both still unchecked in STATUS.md's prerequisites) and running one real `POST /channels/ai_carryon/generate` — several phases' worth of "not yet verified against real services" has now accumulated.

## Checkboxes ticked this session

- [x] `backend/ai/rag/chunker.py` — 300–500 token chunks with overlap (Ch.09)
- [x] `backend/ai/rag/embed.py` — embedding client
- [x] `backend/ai/rag/retriever.py` — hybrid search (vector similarity + keyword overlap, Ch.09)
- [x] Create the 9 Qdrant collections from Ch.10: `scripts`, `research`, `comments`, `viewer_feedback`, `competitors`, `analytics`, `knowledge`, `prompt_history`, `lessons_learned`
- [x] Wire `backend/ai/agents/research_agent.py` to call the retriever before calling the LLM (fig 5.1's flow)
- [x] Backfill: embed and load a handful of past scripts/research from the *old* pipeline into `scripts` and `research` collections, so retrieval has something to find on day one
