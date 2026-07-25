# backend/

Organized by **responsibility**, not by technology. Five top-level folders — keep it that way.

| Folder | What lives here |
|---|---|
| `app/` | The FastAPI app itself: routers, middleware, shared core infra clients, business services, data models (API/Firestore schemas), database access, background workers |
| `ai/` | Everything LLM/agent-related: LangGraph graph + agents, tool definitions, model registry/routing, RAG/retrieval, memory, prompt library |
| `tenant_platform/` | Multi-tenant SaaS plumbing: channel brain, channel factory, workspace onboarding, scheduler, monitoring, tenant isolation & permissions. (Named `tenant_platform/`, not `platform/` as the SAD's prose calls it — `platform` collides with the Python stdlib module of the same name; see `tenant_platform/README.md`.) |
| `integrations/` | Thin clients for external services: Firebase, YouTube, Gemini, OpenAI, Groq |
| `configs/` | Per-channel configuration and encrypted provider-key storage |

Each subfolder has its own `README.md` saying which phase(s) in `../phases/` own it — see `../phases/` for the actual task lists, this file is just the map.

## Two pairs worth not confusing

- **`app/models/` vs `ai/models/`** — `app/models/` is API request/response schemas and Firestore
  document shapes. `ai/models/` is the model *registry*: which LLM handles which task, fallback
  chains across providers, a normalized interface agents code against. Agents should import from
  `ai/models/`, not reach into `integrations/` directly.
- **`ai/models/` vs `integrations/{gemini,openai,groq}/`** — `integrations/` are the raw,
  provider-specific API clients (auth, request formatting, the actual HTTP call). `ai/models/`
  sits on top and decides *which* client to call.

## The guardrail

This project is going to get large. **Don't let `backend/` sprawl past this shape.** If a new concern doesn't obviously fit one of the five folders above, that's a signal to extend an existing folder (e.g. a new integration → `integrations/<name>/`) rather than inventing a sixth top-level category. A backend with 120 loose folders is harder to onboard into than one with five, however deep each goes.

Also: **an empty folder isn't a folder as far as git is concerned.** Every leaf folder here has a `README.md` for a reason — git doesn't track empty directories, so a folder with nothing in it silently disappears on the next commit/clone. If you add a new subfolder, add at least a `README.md` to it in the same commit.
