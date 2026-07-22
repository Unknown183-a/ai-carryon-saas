<!-- Self-contained phase brief. Companion docs: ../../BUILD_GUIDE.md (full build order) and ../../docs/architecture/AI-CarryON-Architecture.html (the why). -->

## Phase 5 — Qdrant + RAG
*(SAD reference: Chapters 09–10 — RAG Deep Dive, Qdrant)*

**Goal:** the Research Agent from Phase 4 retrieves grounded context from Qdrant instead of raw web search alone.

**Depends on:** Phase 4.

**Tasks:**
- [ ] `backend/ai/rag/chunker.py` — 300–500 token chunks with overlap (Ch.09)
- [ ] `backend/ai/rag/embed.py` — embedding client
- [ ] `backend/ai/rag/retriever.py` — hybrid search (vector similarity + keyword overlap, Ch.09)
- [ ] Create the 9 Qdrant collections from Ch.10: `scripts`, `research`, `comments`, `viewer_feedback`, `competitors`, `analytics`, `knowledge`, `prompt_history`, `lessons_learned`
- [ ] Wire `backend/ai/agents/research_agent.py` to call the retriever before calling the LLM (fig 5.1's flow)
- [ ] Backfill: embed and load a handful of past scripts/research from the *old* pipeline into `scripts` and `research` collections, so retrieval has something to find on day one

**Definition of Done:** a research run returns a summary that visibly cites retrieved chunks, and querying Qdrant directly shows points landing in the correct collection with correct metadata.

**Handoff Notes:**
> _(empty — fill in if you stop here)_

---
