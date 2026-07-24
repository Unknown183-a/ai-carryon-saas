<!-- Self-contained phase brief. Companion docs: ../../BUILD_GUIDE.md (full build order) and ../../docs/architecture/AI-CarryON-Architecture.html (the why). -->

## Phase 4 — LangGraph, Single Hardcoded Channel
*(SAD reference: Chapters 04–08 — LangGraph, Research Agent, Planner, Parallel Generation, Review)*

**This is the highest-risk phase in the whole build — budget the most time here.**

**Goal:** one hardcoded channel runs the full graph — Trend → Research → Planner → Parallel(6) → Review — and produces a reviewed script + SEO + thumbnail brief, still without rendering or multi-tenancy.

**Depends on:** Phase 3 (agents will use Redis caching).

**Tasks:**
- [x] Install LangGraph: `pip install langgraph`
- [x] `backend/ai/langgraph/graph.py` — define the `StateGraph` with the node sequence from Ch.04's diagram
- [x] `backend/ai/langgraph/state.py` — the shared state schema (topic, research_summary, planner_json, per-agent outputs)
- [x] Built fresh (no `agents_cricket`/`agents_hindi` code existed to port — confirmed with the repo owner before starting):
  - [x] `backend/ai/agents/trend_agent.py` — Google Trends via pytrends, Redis-cached (`trend:*`, 6h, Ch.11)
  - [x] `backend/ai/agents/research_agent.py` — Serper web search + LLM grounding (RAG/Qdrant deferred to Phase 5 per this brief), Redis-cached (`research:*`, 24h, Ch.11)
  - [x] `backend/ai/agents/planner_agent.py` — outputs the JSON contract from Ch.06
  - [x] `backend/ai/agents/script_agent.py`, `seo_agent.py`, `thumbnail_agent.py`, `hook_agent.py`, `tags_agent.py`, `description_agent.py` — registered as parallel LangGraph nodes (Ch.07)
  - [x] `backend/ai/agents/review_agent.py` — Grammar → Fact → Copyright checks, in order, plus the LLM Judge step from Ch.08
- [x] Wire the conditional retry edge: Review failure routes back to the specific failing Parallel agent, capped at 3 retries (Ch.04)
- [x] `POST /channels/{id}/generate` in FastAPI calls `graph.ainvoke(state)` (Ch.03's "How FastAPI talks to LangGraph")
- [x] Hardcode one channel's config in code (no database-driven config yet) — the real "AI carryON" channel (@AIcarryONAI), per the repo owner's direction

**Definition of Done:** calling `POST /channels/{id}/generate` end-to-end produces a reviewed script + SEO + thumbnail brief in the response, and a forced Review failure demonstrably retries the correct single agent, not all six.

**Handoff Notes:**
> **Read this before touching this phase again — it's the most likely place for a mid-work handoff, so this is deliberately thorough.**
>
> **What's built and verified:** the full graph — `trend → research → planner → [script, seo, thumbnail, hook, tags, description] → review`, with a conditional retry edge — compiles and runs correctly. `tests/phase4_langgraph_test.py` proves both halves of the Definition of Done with everything external faked (no real API keys needed to run it): (1) a full happy-path run through the real `POST /channels/ai_carryon/generate` endpoint returns `status: reviewed`, `review_verdict: pass`, and populated script/seo/thumbnail_brief/hook/tags/description; (2) a forced failure targeting `seo` results in `seo`'s real-work call count being 2 (initial + 1 retry) while all five other writer agents show exactly 1 — proving only the failing agent re-ran, not all six.
>
> **The one non-obvious design decision in this whole phase — read this before changing `graph.py`:** LangGraph's multi-source `add_edge([...], target)` is an AND-join — `target` only fires once *every* listed source node has completed in the *same* superstep. The six Parallel Generation agents all feed into `review` this way, which is correct for the first pass. But if a retry routed straight back to just the one failing agent (say, `seo`), the AND-join watching all six would never re-arm — `seo` would run, but since `script`/`thumbnail`/`hook`/`tags`/`description` don't also fire that round, `review`'s join condition ("all six fired this round") is never satisfied again, and the graph silently stops advancing past `review` with no error. I hit this for real with a throwaway prototype before writing any production code — it's not a hypothetical. **The fix:** a `retry_dispatch` node that always fans out to all six agents again on retry (re-arming the join), but each agent checks `ai.agents._utils.retry_skip(state, its_own_name)` first and returns instantly without calling an LLM unless it's the actual named `retry_target`. So all six nodes technically "run" every retry pass, but only the failing one does real (expensive) work — verified by the call-count assertions in the test script. **Do not "simplify" this back to a direct single-agent retry edge without re-reading this note; it will silently break in a way that's easy to miss (no exception, no error, the graph just stops one step short of `review` on the second pass).**
>
> **Provider-agnostic LLM client, as requested:** `backend/ai/models/llm_client.py` is the layer every agent calls through — `call_llm(model="gemini/gemini-flash-latest", ...)` or just `call_llm(model="gemini-flash-latest", ...)` (provider auto-detected from the model name via `_KNOWN_MODEL_PREFIXES`). Add a new provider by dropping a thin client in `backend/integrations/<provider>/client.py` and adding one line each to `_PROVIDER_CLIENTS` and `_KNOWN_MODEL_PREFIXES` — no agent code changes. Currently wired: Gemini (via the current `google-genai` SDK — the older `google.generativeai` package is fully deprecated, caught and switched during this phase) and Groq. OpenAI's integration folder is still empty on purpose (no key yet) — trivial to add the same way when there is one. `DEFAULT_FALLBACK_CHAIN` in that file controls what `call_llm` tries next if the first model's provider call raises.
>
> **UPDATE 2026-07-24 — verified for real, end-to-end, with actual keys.** The repo owner set up a real Upstash database and ran `tests/phase4_real_keys_smoke_test.py` against real Gemini, Groq, Serper, and Google Trends. Result: `status: reviewed`, `review_verdict: pass`, and a genuinely good, on-brand script grounded in real breaking AI news from literally days before the test ran (Gemini 3.6 Flash's July 21, 2026 release, Sakana AI's Fugu-Cyber launch) — independently fact-checked afterward via a live web search, not just taken on faith. This closes out the gap flagged below and, as a side effect, also closes Phase 3's real-Upstash gap (same run exercised it for real).
>
> This real run caught two bugs the faked test couldn't have, both now fixed:
> 1. **`gemini-1.5-flash` and `gemini-1.5-pro` are fully retired** — a live 404 from the real API. `DEFAULT_MODELS` now uses Google's auto-updating aliases (`gemini-flash-latest`, `gemini-pro-latest`), which resolve to whatever's current instead of a pinned version that can go stale. Trade-off worth knowing: behavior can shift under you when Google repoints an alias; pin an explicit version instead if reproducibility ever matters more than staying current.
> 2. **`call_llm`'s fallback loop only surfaced the *last* candidate's error.** The real Gemini 404 got hidden behind an unrelated "Groq API key not set" error, which cost real debugging time chasing the wrong problem. Fixed: the final `RuntimeError` now lists every candidate's actual error, not just the last one.
>
> What's still NOT verified from that run, worth knowing: `pytrends`'s real behavior for this niche wasn't directly observed (the run picked its top trend candidate fine, but whether that came from live `related_queries` or the `FALLBACK_TOPICS` static list wasn't checked — add a log line if this matters later). Gemini's JSON mode did correctly return a bare array for the Tags Agent in this run, so that earlier concern is resolved.
>
> ~~**What has NOT been verified — this is the important gap:** everything above was tested with the real Gemini/Groq/Serper calls *faked*... nobody has run this against the real Gemini/Groq/Serper services yet~~ — superseded by the UPDATE above, kept struck through rather than deleted so the history of "this was unverified, then it was verified, here's what broke" stays visible to whoever reads this next.
>
> **Review Agent's `force_fail_agent` test-only hook:** `PipelineState.force_fail_agent` exists purely so the retry path is testable without depending on real LLM Judge behavior being flaky. `POST /channels/{id}/generate` never sets it — it's only used by direct `graph.ainvoke()` calls in tests. If a future phase adds a way to trigger this from the API (e.g. a debug endpoint), make sure it's gated behind something that can never fire in production traffic.
>
> **Review Agent's routing simplification:** Grammar/Fact/Copyright check failures all currently route back to `script` (see `_SCRIPT_LEVEL_CHECK_TARGET` in `review_agent.py`) since those three checks only ever inspect the script (and description). Only the LLM Judge can name any of the six agents as the retry target, since it's the only check that looks at all six outputs holistically. This seemed like the right reading of Ch.08, but if description-specific grammar/copyright issues turn out to be common in practice, it might be worth having those two checks name `description` specifically instead of always defaulting to `script`.
>
> **Not done, and out of scope for this phase on purpose:** no image is rendered for the thumbnail (just a brief — headline text, visual concept, style); no voice/audio; no actual YouTube upload; no multi-channel support (`channel_id` in the URL is checked against exactly one hardcoded ID and 404s otherwise — Phase 6's job); Scheduler/`upload_schedule` isn't enforced (Phase 8); the Alert Agent doesn't exist yet so hitting the 3-retry cap just marks the run `status: failed` with a reason instead of alerting anyone (Phase 10).
>
> **Cost note for the repo owner:** every real run of `POST /channels/ai_carryon/generate` makes up to ~10 real LLM calls (research, planner, 6 writers, up to 4 review checks) plus 1 Serper search — cheap per-run on Gemini Flash / Groq free tiers, but worth knowing before scripting repeated test runs.

---
