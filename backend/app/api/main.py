"""
FastAPI Gateway — app instance, CORS, middleware registration.

Phase 2 (shell only): verifies a Firebase JWT and can read/write one
Firestore document through a real endpoint. No LangGraph yet.

Phase 3: rate limiting is now real, backed by Redis (Upstash) — see
app/api/middleware/rate_limit.py.

Phase 6: /channels is now multi-tenant — POST /channels runs through the
Channel Factory (Ch.12d), and channel-scoped routes are gated by the
Ch.12e Permission Check. /workspaces is new (Ch.12c onboarding).
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware.rate_limit import RateLimitMiddleware
from app.api.routers import channels, workspaces

logger = logging.getLogger(__name__)

app = FastAPI(title="AI CarryON Gateway", version="0.1.0")

# CORS — wide open for now during local development.
# Tighten this to your actual frontend origin(s) before Phase 9 (Deployment).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting — applies to every route, including unauthenticated ones
# like /health (see rate_limit.py for how anonymous callers get keyed).
app.add_middleware(RateLimitMiddleware)

app.include_router(channels.router)
app.include_router(workspaces.router)


@app.on_event("startup")
def _ensure_qdrant_collections() -> None:
    """Phase 5: idempotently creates the nine Ch.10 Qdrant collections if
    they don't exist yet. Logged and swallowed rather than raised — an
    unreachable/unconfigured Qdrant shouldn't prevent the API from
    starting (e.g. local dev without QDRANT_URL set yet); the Research
    Agent already degrades to web-search-only if Qdrant is unavailable
    at request time (see research_agent.py's module docstring).
    """
    from ai.rag.collections import ensure_collections

    try:
        created = ensure_collections()
        if created:
            logger.info("Qdrant collections created: %s", created)
    except Exception as exc:  # noqa: BLE001 — startup must not crash on this
        logger.warning("Could not ensure Qdrant collections at startup: %s", exc)


@app.get("/health")
def health():
    """Polled by the Health Agent in Phase 10. Keep this shape stable."""
    return {"status": "ok"}
