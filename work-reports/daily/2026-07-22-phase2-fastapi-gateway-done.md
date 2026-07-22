# Daily Work Report — 2026-07-22

**Phase:** 2 — FastAPI Gateway (shell only)

**What was done:**
- Built `backend/app/api/main.py`, `backend/app/api/middleware/auth.py`, `backend/app/api/dependencies.py`, `backend/app/api/routers/channels.py`
- Started the server locally with uvicorn and verified end-to-end:
  - `GET /health` → `{"status":"ok"}`
  - `GET /channels` with no/bad token → `401 Unauthorized`
  - Created a throwaway Firebase test user via Identity Toolkit `accounts:signUp`
  - `POST /channels` with a valid JWT → creates a Firestore doc scoped to the user's uid
  - `GET /channels` with the same JWT → correctly lists the created channel

**Status:** Phase 2 Definition of Done fully met.

**Next:** Phase 3 — Redis (Upstash): create an Upstash account, build `redis_client.py`, wire real rate limiting into the stub middleware.
