# backend/

Organized by **responsibility**, not by technology. Five top-level folders — keep it that way.

| Folder | What lives here |
|---|---|
| `app/` | The FastAPI app itself: routers, middleware, shared core infra clients, business services, data models, database access, background workers |
| `ai/` | Everything LLM/agent-related: LangGraph graph + agents, RAG/retrieval, memory, prompt library |
| `platform/` | Multi-tenant SaaS plumbing: channel factory, workspace onboarding, scheduler, monitoring |
| `integrations/` | Thin clients for external services: Firebase, YouTube, Gemini, OpenAI, Groq |
| `configs/` | Per-channel configuration and encrypted provider-key storage |

Each subfolder has its own `README.md` saying which phase(s) in `../phases/` own it — see `../phases/` for the actual task lists, this file is just the map.

## The guardrail

This project is going to get large. **Don't let `backend/` sprawl past this shape.** If a new concern doesn't obviously fit one of the five folders above, that's a signal to extend an existing folder (e.g. a new integration → `integrations/<name>/`) rather than inventing a sixth top-level category. A backend with 120 loose folders is harder to onboard into than one with five, however deep each goes.
