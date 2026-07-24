# Phase 9 — Deployment
# Builds the FastAPI backend (backend/app) into a container that exposes /health.

FROM python:3.11-slim AS base

# System deps only if a later phase needs them (e.g. ffmpeg for the render
# worker in Phase 7). Kept minimal for now — add as phases need them.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first so this layer is cached unless requirements.txt changes.
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend source.
COPY backend/ ./backend/

WORKDIR /app/backend

ENV PYTHONUNBUFFERED=1 \
    PORT=8080

EXPOSE 8080

# Cloud Run injects $PORT; default to 8080 for local docker run.
CMD ["sh", "-c", "uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT}"]
