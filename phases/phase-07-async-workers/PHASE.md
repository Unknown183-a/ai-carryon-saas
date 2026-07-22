<!-- Self-contained phase brief. Companion docs: ../../docs/BUILD_GUIDE.md (full build order) and ../../docs/AI-CarryON-Architecture-Document.html (the why). -->

## Phase 7 — Async Workers (Render, Voice, Upload)
*(SAD reference: Chapter 15 — Cloud Tasks & Workers)*

**Goal:** rendering and uploading happen off the request thread, with retries.

**Depends on:** Phase 6.

**Tasks:**
- [ ] Choose a task queue: Cloud Tasks (if already on GCP) or Celery + Redis broker (faster to start with, since Redis already exists from Phase 3)
- [ ] `backend/workers/voice_worker.py` — port existing TTS logic
- [ ] `backend/workers/render_worker.py` — port existing FFmpeg/MoviePy logic; keep the existing `-crf 28 -threads 1` OOM fix from the old pipeline
- [ ] `backend/workers/upload_worker.py` — port existing YouTube upload logic, including the base64-encoded OAuth credential pattern already proven in the old Railway deployment
- [ ] `backend/workers/thumbnail_worker.py`
- [ ] Wire LangGraph's terminal node to enqueue a task instead of calling these directly (Ch.15)
- [ ] Confirm retry-on-5xx behavior actually retries (kill a worker mid-job, confirm the task re-delivers)

**Definition of Done:** a full pipeline run from Phase 6 results in a rendered, uploaded video, and manually crashing the render worker mid-job results in an automatic retry, not a stuck job.

**Handoff Notes:**
> _(empty — fill in if you stop here)_

---
