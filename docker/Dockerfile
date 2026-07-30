# Phase 9 — Deployment
# Builds the FastAPI backend (backend/app) into a container that exposes /health.
#
# Phase 7 update: this image now also runs the Celery workers (Ch.15) —
# `ffmpeg` (render_worker.py) and `fonts-dejavu-core` (thumbnail_worker.py's
# text rendering, see that file's `_load_font` fallback) are real system
# packages, not pip installs, which is exactly the "add as phases need
# them" this file's own comment anticipated back in Phase 0/9.
#
# One image, two entrypoints: the default CMD below runs the API; a
# worker container overrides CMD with the celery invocation (see
# docker-compose.yml / deployment docs, Phase 9's job to finalize) —
# `celery -A app.workers.celery_app worker --loglevel=info`. Not
# duplicating the whole image build for a second Dockerfile, since both
# processes need the identical backend/ source and requirements.txt.

FROM python:3.11-slim AS base

# System deps: build-essential for any pip package needing to compile;
# ffmpeg for render_worker.py; fonts-dejavu-core for thumbnail_worker.py
# (DejaVuSans-Bold.ttf — its own `_load_font` degrades gracefully without
# this, but a real deployment shouldn't rely on the degraded path).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first so this layer is cached unless requirements.txt changes.
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend source.
COPY backend/ ./backend/

WORKDIR /app/backend

ENV PYTHONUNBUFFERED=1 \
    PORT=8080 \
    PYTHONPATH=/app/backend

EXPOSE 8080

# Cloud Run injects $PORT; default to 8080 for local docker run.
# Worker containers override this CMD — see module comment above.
CMD ["sh", "-c", "uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT}"]
