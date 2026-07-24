# Work Report — 2026-07-24

**Phase worked on:** Phase 4 — LangGraph, Single Hardcoded Channel
**Author:** Claude
**Time spent:** ~3 hrs (highest-risk phase per its own brief — took the time)

## What I built / did

**Core graph:**
- `backend/ai/langgraph/state.py` — shared `PipelineState` TypedDict
- `backend/ai/langgraph/graph.py` — the full `StateGraph`: `trend → research → planner → [script, seo, thumbnail, hook, tags, description] → review`, with a conditional retry edge
- `backend/ai/langgraph/hardcoded_channel.py` — the one hardcoded channel for this phase, modeled on the real "AI carryON" YouTube channel per the repo owner's direction

**Agents (all built fresh — confirmed with the repo owner beforehand that no `agents_cricket`/`agents_hindi` code exists anywhere to port):**
- `trend_agent.py` — Google Trends via `pytrends`, seeded from the channel's category, Redis-cached (`trend:*`, 6h). Falls back to a small static evergreen-topics list if pytrends fails or returns nothing.
- `research_agent.py` — Serper web search + LLM grounding (RAG/Qdrant deferred to Phase 5 per this brief). Redis-cached (`research:*`, 24h), with a stale-cache fallback if the live path fails entirely, and retry-with-backoff (2 retries) on both the search call and the summarization call.
- `planner_agent.py` — outputs the Ch.06 JSON contract, validates required keys are present.
- `script_agent.py`, `seo_agent.py`, `thumbnail_agent.py`, `hook_agent.py`, `tags_agent.py`, `description_agent.py` — the six Parallel Generation agents (Ch.07).
- `review_agent.py` — Grammar → Fact → Copyright checks (short-circuit on first failure) → LLM Judge, per Ch.08. Retry cap at 3 per agent; exceeding it marks the run `failed` instead of looping forever (no Alert Agent yet — that's Phase 10).

**Supporting infra:**
- `backend/ai/models/llm_client.py` — the provider-agnostic LLM interface the repo owner asked for: name a model (bare or `provider/model`), it auto-detects Gemini vs. Groq and calls the right thin client, with a fallback chain.
- `backend/integrations/gemini/client.py`, `backend/integrations/groq/client.py` — thin provider clients.
- `backend/ai/tools/web_search.py` — Serper.dev wrapper.
- `backend/ai/prompts/prompt_library.py` — every agent's system prompt in one place.
- `POST /channels/{id}/generate` wired into `backend/app/api/routers/channels.py`.
- `tests/phase4_langgraph_test.py` — full pipeline test, everything external faked.

## What's now working (proof, not vibes)

Running `python tests/phase4_langgraph_test.py`:
```
=== Test 1: full pipeline happy path via POST /channels/ai_carryon/generate ===
✅ status == reviewed
✅ review_verdict == pass
✅ script present / seo present / thumbnail_brief present / hook present / tags present / description present
✅ Test 1 PASSED
✅ Unknown channel_id correctly returns 404

=== Test 2: forced Review failure retries exactly one agent ===
Real LLM call counts: {'Planner Agent': 1, 'Description Agent': 1, 'Hook Agent': 1, 'Script Agent': 1,
                       'SEO Agent': 2, 'Tags Agent': 1, 'Thumbnail Agent': 1, 'Grammar Check': 1,
                       'Fact Check': 1, 'Copyright Check': 1, 'LLM Judge': 1}
✅ Run eventually reached review_verdict == pass
✅ script/thumbnail/hook/tags/description: expected 1, got 1 — seo: expected 2, got 2
✅ Test 2 PASSED
```
Bonus, unplanned proof: Test 2 shows no "Research Agent" entry at all — its output from Test 1 was served straight from the Redis cache (`research:*`, 24h TTL) rather than re-calling the LLM, confirming the caching layer works, not just the retry logic.

## The one thing that would have silently broken this phase

LangGraph's multi-source `add_edge([...], target)` is an AND-join — it only fires once *every* listed source has completed in the *same* superstep. I built a throwaway prototype early (before writing any production code) that routed retries straight back to just the failing agent, and it broke silently: the join watching all six never re-armed, so the graph just stopped advancing past `review` on the second pass, with no exception at all. Full details and the fix (a `retry_dispatch` node that re-fans to all six agents every retry, each of which internally skips real work unless it's the actual retry target) are in `graph.py`'s module docstring and this phase's `PHASE.md` handoff notes — flagged there as the single most important thing to read before changing this file again.

## What broke / what I couldn't finish

- **Nothing has been tested against the real Gemini, Groq, Serper, or Google Trends services.** This sandbox's network egress is allow-listed to package registries and GitHub only — it can't reach `generativelanguage.googleapis.com`, `api.groq.com`, `google.serper.dev`, or `trends.google.com`. Everything above is verified with all four faked in-process. The repo owner has real Gemini and Groq keys and a real Serper key in `.env` already; someone needs to run `POST /channels/ai_carryon/generate` for real and read the actual output quality before trusting this beyond local dev.
- Relatedly, unverified in practice: whether Gemini's JSON mode reliably returns a bare JSON array for the Tags Agent, and whether `pytrends`'s `related_queries` actually returns anything useful for a niche category like "AI, coding, and future technology" or just falls back to the static list every time.

## Decisions made (and why)

- **No existing pipeline code to port** — confirmed directly with the repo owner before starting (the brief's mention of `agents_cricket`/`agents_hindi` referred to code that was never actually written into this repo). Built all agents fresh from the architecture doc instead.
- **Switched Gemini's client to the current `google-genai` SDK** instead of `google.generativeai` — caught a `FutureWarning` mid-build that the older package is fully deprecated (no more updates or bug fixes), so building on it now would have been choosing a dead end on day one.
- **Hardcoded channel modeled on the real "AI carryON" YouTube channel** (@AIcarryONAI, AI/coding/future-tech, English, Shorts format) — per the repo owner's direction, rather than an arbitrary placeholder.
- **Provider-agnostic model registry** (`backend/ai/models/llm_client.py`) resolves bare model names to a provider via known prefixes, per the repo owner's explicit request: "just name the AI model and API key, the system auto-detects."
- **Grammar/Fact/Copyright check failures all route to `script`** rather than trying to have those three checks name any of the six agents — they only ever inspect the script (and description). Only the LLM Judge, which looks at all six outputs holistically, can name a different agent as the retry target. Flagged in the handoff notes as worth revisiting if description-specific issues turn out to be common.
- **`force_fail_agent` test-only hook** on `PipelineState`, never set by real traffic, exists purely so the retry path is deterministically testable without depending on the real LLM Judge's behavior.

## Next concrete step

Phase 5 — Qdrant + RAG (the Research Agent gets real retrieval instead of plain web search). Before that, ideally: run this phase's pipeline for real once with actual keys and eyeball the output quality — flagged as the open item in `STATUS.md`.

## Checkboxes ticked this session

All of Phase 4's tasks in both `phases/phase-04-langgraph-core-agents/PHASE.md` and the mirrored checklist in `BUILD_GUIDE.md`. Also caught and fixed a gap from last session: Phase 3's checkboxes in `BUILD_GUIDE.md` had been left unticked even though the phase was done — fixed those too.
