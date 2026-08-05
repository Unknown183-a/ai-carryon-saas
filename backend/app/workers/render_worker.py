"""
Render Worker -- updated to stitch together background video clips
fetched by clips_worker.py (Pexels stock footage) instead of the
original single-static-thumbnail Ken Burns zoom. The thumbnail PNG is
untouched -- still generated separately and passed to upload_worker.py
for YouTube's thumbnail slot only, matching the base project's
image_agent.py / thumbnail_agent.py separation.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

from app.workers.celery_app import celery_app
from app.workers.storage import ensure_local, persist, run_dir

TARGET_SIZE = (1080, 1920)


def _audio_duration_seconds(audio_path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", audio_path],
        check=True,
        capture_output=True,
        timeout=30,
    )
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def _build_filter_complex(clip_count: int, per_clip_seconds: float) -> str:
    w, h = TARGET_SIZE
    parts = []
    concat_inputs = []
    for i in range(clip_count):
        parts.append(
            f"[{i}:v]trim=duration={per_clip_seconds:.3f},setpts=PTS-STARTPTS,"
            f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}[v{i}]"
        )
        concat_inputs.append(f"[v{i}]")
    concat_line = "".join(concat_inputs) + f"concat=n={clip_count}:v=1:a=0[outv]"
    return ";".join(parts) + ";" + concat_line


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

    # audio_path/clip_paths may be `firebase://...` references written by
    # a different (possibly since-recycled) container — resolve each to a
    # local file on *this* container before handing anything to ffmpeg,
    # which only understands local paths.
    audio_path = str(ensure_local(payload["audio_path"], channel_id, run_id))
    clip_paths: list[str] = [
        str(ensure_local(p, channel_id, run_id)) for p in payload["clip_paths"]
    ]

    output_path = run_dir(channel_id, run_id) / "final.mp4"

    duration = _audio_duration_seconds(audio_path)
    per_clip_seconds = duration / len(clip_paths)
    filter_complex = _build_filter_complex(len(clip_paths), per_clip_seconds)

    command = ["ffmpeg", "-y"]
    for clip_path in clip_paths:
        command += ["-i", clip_path]
    command += ["-i", audio_path]

    audio_input_index = len(clip_paths)
    command += [
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", f"{audio_input_index}:a",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-crf", "28",
        "-threads", "1",
        "-pix_fmt", "yuv420p",
        "-shortest",
        str(output_path),
    ]

    subprocess.run(command, check=True, capture_output=True, timeout=15 * 60)
    storage_ref = persist(output_path, channel_id, run_id)

    return {**payload, "video_path": storage_ref}
