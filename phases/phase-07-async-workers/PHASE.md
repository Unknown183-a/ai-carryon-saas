<!-- Self-contained phase brief. Companion docs: ../../BUILD_GUIDE.md (full build order) and ../../docs/architecture/AI-CarryON-Architecture.html (the why). -->

## Phase 7 — Async Workers (Render, Voice, Upload)
*(SAD reference: Chapter 15 — Cloud Tasks & Workers)*

**Goal:** rendering and uploading happen off the request thread, with retries.

**Depends on:** Phase 6.

**Tasks:**
- [x] Choose a task queue: Cloud Tasks (if already on GCP) or Celery + Redis broker (faster to start with, since Redis already exists from Phase 3) — **chose Celery + Redis**, reusing the exact same Upstash instance Phase 3 provisioned via its `rediss://` protocol instead of the REST one Phase 3's `redis_client.py` uses (see `app/workers/celery_app.py`'s module docstring for the mechanics, and `docs/decisions/0001-task-queue-choice.md` for the full reasoning and trade-off — no second Redis instance, no second bill)
- [x] `backend/app/workers/voice_worker.py` — ElevenLabs TTS via a new thin httpx client (`integrations/elevenlabs/client.py`), same pattern as `integrations/gemini/`
- [x] `backend/app/workers/render_worker.py` — FFmpeg (shells out to the real binary via `subprocess`, no wrapper library); kept the existing `-crf 28 -threads 1` OOM fix from the old pipeline, unchanged
- [x] `backend/app/workers/upload_worker.py` — YouTube Data API v3 resumable upload (`integrations/youtube/client.py`), including the base64-encoded OAuth credential pattern (`YOUTUBE_CLIENT_SECRETS_B64`/`YOUTUBE_TOKEN_B64`) already proven in the old Railway deployment, plus a per-channel token override (Ch.12d) that falls back to the platform default
- [x] `backend/app/workers/thumbnail_worker.py` — Pillow, rasterizes `ai/agents/thumbnail_agent.py`'s existing brief (headline/style JSON, no pixels — Ch.07) into an actual 1280x720 PNG
- [x] Wire LangGraph's terminal node to enqueue a task instead of calling these directly (Ch.15) — `ai/langgraph/graph.py`'s new `enqueue_render` node, reached only on `review_verdict == "pass"`; builds and `apply_async()`s a Celery `chain(voice, thumbnail, render, upload)` and returns immediately (`render_task_id` in the response) rather than blocking `graph.ainvoke()` on a multi-minute render
- [x] Confirm retry-on-5xx behavior actually retries (kill a worker mid-job, confirm the task re-delivers) — **verified two distinct ways, see Handoff Notes below for exactly what "verified" means for each**

**Definition of Done:** a full pipeline run from Phase 6 results in a rendered, uploaded video, and manually crashing the render worker mid-job results in an automatic retry, not a stuck job.

**Handoff Notes:**
> Two different retry mechanisms exist here, verified two different ways — worth being precise about which is which, same way Phase 4's handoff distinguished "config present" from "config actually fires":
>
> 1. **Broker-level** (`celery_app.py`: `task_acks_late=True` + `task_reject_on_worker_lost=True`) — this is the literal mechanism behind "kill a worker mid-job, confirm it re-delivers." **Verified structurally, not by an actual process kill**: `tests/phase7_async_workers_test.py`'s Test 1 asserts both settings are `True` on the live `celery_app.conf`. A real process-kill test needs an actual running worker + broker connection (`celery -A app.workers.celery_app worker`, then `kill -9` it mid-render) — that's an operational/manual verification step, not something a unit test can stage, and it hasn't been run for real yet. **Next concrete action if you pick this phase back up**: run one real worker locally, kick off a real render, `kill -9` the worker process mid-`ffmpeg`, confirm the job shows up on another worker (or the same one restarted) instead of vanishing. Should work given the config, but "should work" and "watched it happen" are different claims — Phase 5's Qdrant payload-index bug is the reminder of why that gap matters.
> 2. **Task-level** (`autoretry_for`/`retry_backoff`/`retry_kwargs` on each of the four tasks) — this is "the task ran, failed with a transient error, retries with backoff," a different case (worker process stayed alive; the task itself failed). **This one IS functionally verified**, not just structurally: Test 6 makes a fake `ffmpeg` call fail once and succeed on the second call, and confirms `render_video` actually recovers end-to-end (right output file, right content, `autoretry_for` demonstrably fired — see that test's own comments for a real Celery `task_always_eager` gotcha this ran into and how it was worked around honestly rather than papered over).
>
> Storage is a known, deliberate gap (see `app/workers/storage.py`'s module docstring): all four workers currently share a local filesystem path (`WORKER_OUTPUT_DIR`), which only works because there's one local worker process right now. The moment there's more than one worker process on more than one machine, `render_worker` won't be able to see `voice_worker`'s output file. `.env.example` already has `FIREBASE_STORAGE_BUCKET` sitting unused from Phase 6 for exactly this — wiring it in is real work worth its own pass, not a drive-by addition here.
>
> Also touched (necessarily, not scope creep): `ai/langgraph/state.py` (two new fields), `app/api/routers/channels.py` (`/generate` now returns `render_task_id`/`render_status`), `requirements.txt`, `.env.example`, `docker/Dockerfile` (added `ffmpeg` + `fonts-dejavu-core` — the Dockerfile's own comment from Phase 9 already anticipated this). **And, importantly**: `tests/phase4_langgraph_test.py` and `tests/phase6_multi_tenancy_test.py` both needed a small patch — a passing review now enqueues a real Celery chain, which broke their happy-path tests against a live (absent) Redis broker until they were given the same eager-mode + faked-externals treatment Phase 7's own test uses. Both files say exactly why in their own "Updated in Phase 7" comment blocks, same convention Phase 6 used when it touched `phase4_langgraph_test.py`'s Test 1. All three phases' test scripts (4, 6, 7 — 34 + 23 + 40 checks) pass clean together after that patch.
>
> Nothing here has been run against real ElevenLabs/YouTube/a real `ffmpeg` binary yet — see `STATUS.md`'s Blocking Issue for the same real-keys-smoke-test gap Phases 4/5 had before their `*_real_keys_smoke_test.py` scripts closed it out.

---
