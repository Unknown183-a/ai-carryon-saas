Owned by: **Phase 4 — langgraph-core-agents**.

LangGraph tool definitions agents call mid-reasoning (e.g. web search, trend lookup, a calculator).
Distinct from `backend/ai/agents/` (the agents themselves) and `backend/integrations/` (raw external
API clients) — a tool here is typically a thin wrapper around one or more integrations, exposed in
the shape LangGraph expects.

See `../../../phases/` for that phase's full brief.
