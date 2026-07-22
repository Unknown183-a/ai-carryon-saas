<!-- Self-contained phase brief. Companion docs: ../../BUILD_GUIDE.md (full build order) and ../../docs/architecture/AI-CarryON-Architecture.html (the why). -->

## Phase 2 — FastAPI Gateway (shell only)
*(SAD reference: Chapter 03 — FastAPI Gateway)*

**Goal:** a running FastAPI app that verifies a Firebase JWT and can read/write one Firestore document through a real endpoint — no LangGraph yet.

**Depends on:** Phase 1.

**Tasks:**
- [ ] `backend/app/api/main.py` — app instance, CORS, middleware registration
- [ ] `backend/app/api/middleware/auth.py` — verifies `Authorization: Bearer <jwt>` against Firebase Admin SDK
- [ ] `backend/app/api/dependencies.py` — `Depends()` providers for current user + Firestore client
- [ ] `backend/app/api/routers/channels.py` — `GET /channels` (list), `POST /channels` (create, no factory logic yet — just a raw Firestore write)
- [ ] `GET /health` endpoint returning `{"status": "ok"}` — this is what the Health Agent (Phase 10) will poll later, build the shape now
- [ ] Rate limiter middleware is a stub for now (real logic in Phase 3)

**Definition of Done:** `curl` with a valid Firebase JWT successfully creates and lists a channel document; `curl` with no token or a bad token gets `401`.

**Handoff Notes:**
> _(empty — fill in if you stop here)_

---
