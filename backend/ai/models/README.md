Owned by: **Phase 4 — langgraph-core-agents** (first use), refined in **Phase 6 — multi-tenancy-channel-factory** (per-channel model selection).

**Model registry / provider-agnostic LLM interface layer.** This is where an agent asks for
"the best model for this task" and gets back a normalized response — not where the raw provider
API calls happen.

Contains things like:
- Model registry (which model handles which task: script writing vs. cheap classification)
- Fallback/retry chains across providers (Gemini → Groq → OpenAI)
- A normalized request/response interface agents code against, so swapping a provider doesn't touch agent code
- Per-channel model preference resolution (Ch.12d — a channel picks a model, this layer honors it)

**How this differs from `backend/integrations/{gemini,openai,groq}/`:** those folders are the thin,
provider-specific clients — auth, request formatting, rate limits, the actual HTTP call. This folder
sits on top of them and decides *which* client to call. Agents in `backend/ai/agents/` should import
from here, not reach into `integrations/` directly.

See `../../../phases/` for that phase's full brief.
