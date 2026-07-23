"""
FastAPI Gateway — app instance, CORS, middleware registration.

Phase 2 (shell only): verifies a Firebase JWT and can read/write one
Firestore document through a real endpoint. No LangGraph yet.

Phase 3: rate limiting is now real, backed by Redis (Upstash) — see
app/api/middleware/rate_limit.py.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware.rate_limit import RateLimitMiddleware
from app.api.routers import channels

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


@app.get("/health")
def health():
    """Polled by the Health Agent in Phase 10. Keep this shape stable."""
    return {"status": "ok"}
