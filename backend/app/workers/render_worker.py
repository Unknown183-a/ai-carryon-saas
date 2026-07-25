"""
Render Worker (Ch.15: "Video rendering... Worker (FFmpeg)... 1-4 minutes"
— by far the slowest job in the chain, which is the whole reason this
phase exists: this can't run inside an HTTP request-response cycle).

Combines this run's audio (voice_worker) and thumbnail image
(thumbnail_worker) into a finished MP4 — a Ken Burns-style slow zoom on
the still thumbnail for the audio's full duration, silence-padded frame
so `ffmpeg -shortest` never clips the voiceover a frame early. Shells
out to the real `ffmpeg` binary via `subprocess` rather than a Python
wrapper library (ffmpeg-python, moviepy) — this project's established
convention for external processes/services (see qdrant_client.py's
module docstring: thin wrapper over the real thing beats a heavier SDK
at this project's scale) extends naturally to "call the real CLI
tool directly" here too.

**"keep the existing `-crf 28 -threads 1` OOM fix from the old
pipeline"** (this phase's PHASE.md) — ported unchanged, per this
project's history: "FFmpeg OOM fix: `-crf 28 -threads 1`, combined
concat+scale into single pass." `-threads 1` caps FFmpeg's own internal
parallelism so it doesn't spawn enough encoder threads to blow past a
memory-constrained worker's limit (the old pipeline's dev machine was an
8GB-RAM MacBook Air, per this project's build history — the same
constraint likely applies to a small/free-tier worker container here).
`-crf 28` trades a little visual quality for a smaller intermediate
buffer than FFmpeg's default `-crf 23`. Both flags are cheap insurance
that cost nothing on a beefier machine and prevent a real, previously-hit
OOM kill on a small one — kept exactly as before rather than re-tuned,
since there's no new evidence to tune against yet.
"""

from __future__ import annotations

import subprocess
from typing import Any

from app.workers.celery_app import celery_app
from app.workers.storage import run_dir

# Ken Burns zoom: a slow linear zoom-in over the clip's full length.
# 1.0 -> ~1.08 over a typical 45s Short is a subtle, non-nauseating
# amount of motion on a still image — matches the "Ken Burns zoom" note
# in this project's video-quality history without over-animating it.
_ZOOM_FILTER = "zoompan=z='min(zoom+0.0007,1.08)':d=1:s=1080x1920:fps=30"


@celery_app.task(
    name="workers.render_video",
    autoretry_for=(subprocess.CalledProcessError, subprocess.TimeoutExpired),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_kwargs={"max_retries": 2},
)
def render_video(payload: dict[str, Any]) -> dict[str, Any]:
    channel_id = payload["channel_id"]
    run_id = payload["run_id"]
    audio_path = payload["audio_path"]
    thumbnail_path = payload["thumbnail_path"]

    output_path = run_dir(channel_id, run_id) / "final.mp4"

    # Single-pass: loop the still image, apply the zoompan filter, mux in
    # the voice track, stop at whichever stream is shorter (the padded
    # image loop, effectively -shortest lets the audio determine length).
    command = [
        "ffmpeg",
        "-y",  # overwrite output_path if a previous attempt left one (retry-safe)
        "-loop", "1",
        "-i", thumbnail_path,
        "-i", audio_path,
        "-vf", _ZOOM_FILTER,
        "-c:v", "libx264",
        "-c:a", "aac",
        "-crf", "28",
        "-threads", "1",
        "-pix_fmt", "yuv420p",
        "-shortest",
        str(output_path),
    ]

    subprocess.run(
        command,
        check=True,
        capture_output=True,
        timeout=15 * 60,  # generous ceiling well above the ~1-4 min typical duration (Ch.15's table)
    )

    return {**payload, "video_path": str(output_path)}
