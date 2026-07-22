<!-- Self-contained phase brief. Companion docs: ../../docs/BUILD_GUIDE.md (full build order) and ../../docs/AI-CarryON-Architecture-Document.html (the why). -->

## Phase 4 — LangGraph, Single Hardcoded Channel
*(SAD reference: Chapters 04–08 — LangGraph, Research Agent, Planner, Parallel Generation, Review)*

**This is the highest-risk phase in the whole build — budget the most time here.**

**Goal:** one hardcoded channel runs the full graph — Trend → Research → Planner → Parallel(6) → Review — and produces a reviewed script + SEO + thumbnail brief, still without rendering or multi-tenancy.

**Depends on:** Phase 3 (agents will use Redis caching).

**Tasks:**
- [ ] Install LangGraph: `pip install langgraph`
- [ ] `backend/langgraph/graph.py` — define the `StateGraph` with the node sequence from Ch.04's diagram
- [ ] `backend/langgraph/state.py` — the shared state schema (topic, research_summary, planner_json, per-agent outputs)
- [ ] Port existing `agents_cricket`/`agents_hindi` logic into `backend/agents/`:
  - [ ] `trend_agent.py` — reuse existing Google Trends logic, wrap Redis caching (`trend:*`, Ch.11)
  - [ ] `research_agent.py` — reuse existing research logic; RAG/Qdrant wiring deferred to Phase 5, use plain web search for now
  - [ ] `planner_agent.py` — new: outputs the JSON contract from Ch.06
  - [ ] `script_agent.py`, `seo_agent.py`, `thumbnail_agent.py`, `hook_agent.py`, `tags_agent.py`, `description_agent.py` — port from existing pipeline, register as parallel LangGraph nodes (Ch.07)
  - [ ] `review_agent.py` — port the existing grammar/fact/copyright checks; add the LLM Judge step from Ch.08
- [ ] Wire the conditional retry edge: Review failure routes back to the specific failing Parallel agent, capped at 3 retries (Ch.04)
- [ ] `POST /channels/{id}/generate` in FastAPI calls `graph.ainvoke(state)` (Ch.03's "How FastAPI talks to LangGraph")
- [ ] Hardcode one channel's config in code (no database-driven config yet)

**Definition of Done:** calling `POST /channels/{id}/generate` end-to-end produces a reviewed script + SEO + thumbnail brief in the response, and a forced Review failure demonstrably retries the correct single agent, not all six.

**Handoff Notes:**
> _(empty — fill in if you stop here — **this phase is the most likely place someone will need to hand off mid-work, be extra detailed**)_

---
