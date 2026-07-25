Owned by: **Phase 7 — async-workers**.

Celery tasks (Ch.15), chained voice -> thumbnail -> render -> upload by
`ai/langgraph/graph.py`'s `enqueue_render` terminal node on a passing
review:

- `celery_app.py` — the Celery app instance, broker/retry config
- `storage.py` — shared run-scoped local output dir (documented gap: not yet real cloud storage)
- `voice_worker.py` — TTS via ElevenLabs (`integrations/elevenlabs/`)
- `thumbnail_worker.py` — rasterizes the thumbnail_brief (Ch.07) into a PNG
- `render_worker.py` — FFmpeg: still image + audio -> final MP4 (`-crf 28 -threads 1` OOM fix)
- `upload_worker.py` — YouTube upload (`integrations/youtube/`)

See `../../../phases/phase-07-async-workers/PHASE.md`.
