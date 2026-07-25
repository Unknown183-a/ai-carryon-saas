# Work Report — 2026-07-25

**Phase worked on:** Phase 7 — Async Workers (Render, Voice, Upload)
**Author:** Claude
**Time spent:** ~3 hrs

## What I built / did

**Task queue decision:** Celery + Redis, reusing Phase 3's existing Upstash instance via its `rediss://` protocol (Celery needs the real Redis wire protocol; Phase 3's `redis_client.py` uses Upstash's REST API instead — same database, two protocols, no second instance provisioned). Documented in `celery_app.py`'s module docstring since it's an easy thing to get wrong.

**New modules:**
- `app/workers/celery_app.py` — Celery app; `task_acks_late` + `task_reject_on_worker_lost` for broker-level "survive a dead worker" retry
- `app/workers/storage.py` — shared run-scoped local output dir (documented gap: not yet real cloud storage — see Handoff Notes)
- `app/workers/voice_worker.py`, `thumbnail_worker.py`, `render_worker.py`, `upload_worker.py` — the four chained tasks
- `integrations/elevenlabs/client.py` — thin httpx TTS wrapper, same pattern as `integrations/gemini/`
- `integrations/youtube/client.py` — resumable upload, base64 OAuth pattern from the old Railway deployment, per-channel token override falling back to platform default

**Wiring:**
- `ai/langgraph/graph.py` — new `enqueue_render` terminal node, reached only on `review_verdict == "pass"`; builds a Celery `chain(voice, thumbnail, render, upload)` and `apply_async()`s it, returns immediately rather than blocking on a multi-minute render
- `ai/langgraph/state.py` — added `render_task_id`, `render_status`
- `app/api/routers/channels.py` — `/generate` response now includes both
- `requirements.txt`, `.env.example`, `docker/Dockerfile` (added `ffmpeg` + `fonts-dejavu-core` — the Dockerfile's own Phase 9 comment already anticipated this)

**Tests:**
- `tests/phase7_async_workers_test.py` — new, 40 checks: per-task correctness against faked externals, broker-level retry config verified structurally, task-level retry verified functionally (a fake `ffmpeg` call fails once, task recovers), full chain end-to-end
- `tests/phase4_langgraph_test.py`, `tests/phase6_multi_tenancy_test.py` — both needed a small patch (see What broke, below)

## What's now working (proof, not vibes)

`tests/phase7_async_workers_test.py`, condensed:
```
=== Test 1: broker-level retry guarantee is actually configured ===
✅ task_acks_late is True / task_reject_on_worker_lost is True / worker_prefetch_multiplier is 1

=== Test 2: each task has its own autoretry config ===
✅ all four tasks: autoretry_for, retry_backoff, retry_kwargs.max_retries present and sane
✅ upload_to_youtube retries more than the other three (last step, worth retrying harder)

=== Test 3-5: voice / thumbnail / render, individually ===
✅ real audio file written from faked TTS bytes
✅ real 1280x720 PNG rasterized from the thumbnail_brief
✅ ffmpeg command includes -crf 28 and -threads 1 (the OOM fix, kept)

=== Test 6: render_video retries once on a transient ffmpeg failure and then succeeds ===
✅ the failure actually triggered autoretry_for's Retry (not silently swallowed)
✅ ffmpeg was called twice; final file is from the SECOND (successful) attempt

=== Test 7-8: upload, then the full chain ===
✅ youtube_video_id returned; platform-default token fallback used correctly
✅ full chain: audio_path → thumbnail_path → video_path → youtube_video_id, nothing dropped

40 passed, 0 failed
```

Re-ran Phase 4 and Phase 6's suites afterward: both needed the patch described below; after that, 34/34 and 23/23 pass. All three phases' suites (4, 6, 7 — 97 checks total) pass together in the same run.

## What broke / what I couldn't finish

**Broke, fixed:** `graph.py`'s new `enqueue_render` node meant Phase 4 and Phase 6's happy-path tests — which both legitimately drive a real review-pass — started trying to enqueue a real Celery chain against a live (absent) Redis broker. Fixed by giving both files the same eager-mode + faked-externals treatment Phase 7's own test uses, with a clearly labeled "Updated in Phase 7" comment block in each, same convention Phase 6 used when it touched `phase4_langgraph_test.py`.

**Real Celery gotcha, worked around honestly rather than hidden:** `task_always_eager` doesn't actually loop a retry the way a live worker/broker would — it raises `celery.exceptions.Retry` once. Test 6 catches that and manually issues the one redelivery a real broker would perform, with a comment explaining exactly why, rather than quietly asserting something the test wasn't really proving.

**Not done, not attempted:** nothing here has been run against real ElevenLabs, real YouTube, or a real `ffmpeg` binary yet — same real-keys-smoke-test gap Phases 4/5 had before their own smoke tests closed it out. Also not done: the literal "kill a live worker process mid-job" manual verification — the broker-level retry setting is confirmed structurally (it's `True` in config) but not watched happening in a real crash. Both called out plainly in `STATUS.md` and this phase's `PHASE.md` handoff notes, not glossed over.

**Storage gap, deliberate:** all four workers currently share a local filesystem path — fine for one local worker process, breaks the moment there's more than one worker on more than one machine. `FIREBASE_STORAGE_BUCKET` has sat unused in `.env.example` since Phase 6 for exactly this; wiring it in is real, separate work, not a drive-by addition here.

## Decisions made (and why)

- **Celery + Redis over Cloud Tasks** — PHASE.md's own brief allowed either; Celery+Redis was faster to stand up against infrastructure that already existed (Phase 3's Upstash), and this project isn't committed to GCP yet (Phase 9's deploy target is still an open decision).
- **Shell out to the real `ffmpeg` binary via `subprocess`, not `ffmpeg-python`/`moviepy`** — matches this project's established "thin wrapper over the real thing" convention (see `qdrant_client.py`'s own reasoning), and the old pipeline's `-crf 28 -threads 1` OOM fix is a raw CLI flag anyway.
- **Local disk for intermediate artifacts, not Firebase Storage, this phase** — proving the render+retry Definition of Done doesn't require solving multi-worker file sharing; that's real, distinct scope, deferred on purpose and stated plainly rather than silently assumed away.

## Next concrete step

Run a real end-to-end pass with real `ELEVENLABS_API_KEY`, real `YOUTUBE_CLIENT_SECRETS_B64`/`YOUTUBE_TOKEN_B64`, real `CELERY_BROKER_URL`, and a real local `ffmpeg` binary — then do the literal "start a worker, kill -9 it mid-render, watch it re-deliver" check — before starting Phase 8 (whose scheduled trigger will be the first thing calling `enqueue_render` unattended).

## Checkboxes ticked this session

- [x] Choose a task queue: Cloud Tasks (if already on GCP) or Celery + Redis broker (faster to start with, since Redis already exists from Phase 3)
- [x] `backend/app/workers/voice_worker.py` — port existing TTS logic
- [x] `backend/app/workers/render_worker.py` — port existing FFmpeg/MoviePy logic; keep the existing `-crf 28 -threads 1` OOM fix from the old pipeline
- [x] `backend/app/workers/upload_worker.py` — port existing YouTube upload logic, including the base64-encoded OAuth credential pattern already proven in the old Railway deployment
- [x] `backend/app/workers/thumbnail_worker.py`
- [x] Wire LangGraph's terminal node to enqueue a task instead of calling these directly (Ch.15)
- [x] Confirm retry-on-5xx behavior actually retries (kill a worker mid-job, confirm the task re-delivers) — structurally for the broker-level guarantee, functionally for the task-level one; see Handoff Notes for the precise distinction
