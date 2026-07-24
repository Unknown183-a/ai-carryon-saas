# Work Report — 2026-07-24 (evening)

**Phase worked on:** Phase 4 follow-up — real-keys verification
**Author:** Claude
**Time spent:** ~45 min (mostly guiding the repo owner through Terminal/Upstash setup, plus diagnosing one real bug)

## What happened

The repo owner set up a real Upstash Redis database (closing Phase 3's long-standing open gap) and ran `tests/phase4_real_keys_smoke_test.py` for real — actual Gemini, Groq, Serper, and Google Trends calls, no mocking.

## What broke, and what I fixed

**First run failed** with a `RuntimeError` about `GROQ_API_KEY` not being set. That looked like the whole problem, but it wasn't — it was Groq's *fallback* failing after Gemini had already failed silently first. `call_llm`'s exception handling only surfaced the last candidate's error, hiding the real one.

Isolated the real Gemini call directly (bypassing the fallback chain) and got the actual error: `404 NOT_FOUND — models/gemini-1.5-flash is not found`. Both `gemini-1.5-flash` and `gemini-1.5-pro` are fully retired from the live API.

**Fixed both problems:**
1. Switched every `DEFAULT_MODELS` entry from pinned `gemini-1.5-*` versions to Google's auto-updating aliases (`gemini-flash-latest`, `gemini-pro-latest`), confirmed via web search this is the officially documented way to avoid re-pinning to a version that'll eventually retire again.
2. Fixed `call_llm`'s fallback loop to report *every* candidate's actual error in the final exception, not just the last one — so this class of bug surfaces immediately next time instead of needing a manual isolated repro script.
3. Also added `GROQ_API_KEY` to the real-keys test's required-vars check, since it hadn't been required even though it's part of the fallback chain.

## Second run — full success

```
STATUS: reviewed
REVIEW VERDICT: pass
TOPIC: new AI model release this week
```

Full script, SEO, thumbnail brief, hook, tags, and description all generated, and all four Review gates (grammar, fact, copyright, LLM judge) passed. Independently fact-checked the research summary's specific claims afterward via a live web search (not just trusting the pipeline) — every claim held up: Gemini 3.6 Flash's real July 21, 2026 release, Sakana AI's real Fugu-Cyber launch and its real benchmark comparisons against Fable 5/Mythos, GPT-5.6 Sol's real appearance on live benchmark trackers. The Research Agent correctly grounded on literally days-old breaking news rather than anything fabricated.

## Also resolved (side effect of this run)

The same test run exercised real Upstash for the first time, closing out Phase 3's long-open "no real Upstash account tested against" gap at the same time.

## Unrelated but worth noting

While debugging this, discovered another Claude.ai session (a separate chat, not this one) had independently built and pushed Phase 5 (Qdrant + RAG) in parallel, without prior coordination. Confirmed with the repo owner this was expected (a different tab they'd forgotten to mention), not a security concern — commit authorship (`Claude <claude@anthropic.com>` vs. the repo owner's own real git identity on the Phase 9 commits) made this easy to distinguish from anything unexpected.

## Decisions made (and why)

- **Aliases over pinned versions for Gemini models** — the whole reason this broke in the first place was a pinned version going stale; aliases fix the class of bug, not just this instance. Trade-off flagged in code comments: behavior can shift when Google repoints an alias, so pin explicitly if reproducibility ever matters more than staying current.
- **Surfacing every fallback candidate's error** rather than just the last one — this cost real debugging time by hiding the actual (Gemini) failure behind an unrelated (Groq) one; not doing this again.

## Next concrete step

Phase 6 — Multi-Tenancy: Channel Brain / Factory (per `STATUS.md`, already the active phase — Phase 5 having been completed by the parallel session).
