"""
Voice Worker (Ch.15: "Voice generation... Worker... 10-30 seconds").

First link in the render chain LangGraph's terminal node enqueues (see
`ai/langgraph/graph.py`'s `_enqueue_render` node). Takes the reviewed
pipeline's script, generates spoken audio, writes it to this run's local
output dir (see `storage.py` for why local, for now), and passes the
payload on to `thumbnail_worker` unchanged plus `audio_path`.

`autoretry_for=(Exception,)` here is deliberately as broad as
`ai/agents/_utils.py`'s `retry_with_backoff` — a flaky ElevenLabs call,
a rate limit, a transient network blip should all retry the same way;
narrowing to specific exception types would mean silently NOT retrying
some transient failure this project hasn't hit yet. This is the
task-level retry (the task ran, failed, retries with backoff) — a
different mechanism from `celery_app.py`'s `task_acks_late` /
`task_reject_on_worker_lost` (the task's WORKER died mid-run, gets
redelivered to another worker). Both are needed; see celery_app.py's
module docstring for why they're not redundant with each other.
"""

from __future__ import annotations

from typing import Any

from app.workers.celery_app import celery_app
from app.workers.storage import run_dir
from integrations.elevenlabs.client import generate_speech


@celery_app.task(
    name="workers.generate_voice",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_kwargs={"max_retries": 3},
)
def generate_voice(payload: dict[str, Any]) -> dict[str, Any]:
    """`payload` is the render-chain context built by
    `_enqueue_render` (channel_id, run_id, script, voice_profile,
    seo, tags, description, thumbnail_brief, ...). Returns the same
    dict with `audio_path` added, unmodified otherwise — every later
    worker in the chain needs everything earlier workers didn't touch.
    """
    channel_id = payload["channel_id"]
    run_id = payload["run_id"]
    script = payload["script"]
    voice_profile = payload.get("voice_profile")

    audio_bytes = generate_speech(text=script, voice_profile=voice_profile, channel_id=channel_id)

    audio_path = run_dir(channel_id, run_id) / "voice.mp3"
    audio_path.write_bytes(audio_bytes)

    return {**payload, "audio_path": str(audio_path)}
