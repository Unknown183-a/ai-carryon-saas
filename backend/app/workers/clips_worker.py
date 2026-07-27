"""
Clip Fetch Worker (new -- ports the base ai-carryon project's
image_agent.py background-visuals step, which the SaaS rewrite never
carried over).

Per-channel Pexels key, same pattern as upload_worker.py's YouTube
token: a channel's own stored `pexels_api_key` is used if it supplied
one, falling back to the platform PEXELS_API_KEY env var only when the
channel didn't supply one.
"""

from __future__ import annotations

import os
import re as _re
from typing import Any

import requests

from app.workers.celery_app import celery_app
from app.workers.storage import run_dir

PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"
CLIP_COUNT = 4
PER_PAGE = 1

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "to", "of", "in", "on",
    "for", "and", "or", "with", "at", "by", "this", "that", "it", "its",
    "as", "be", "your", "you", "we", "our", "how", "what", "why",
}


def _channel_pexels_key(channel_id: str) -> str | None:
    try:
        from app.api.dependencies import get_firestore
        from app.database.firestore_collections import get_provider_keys
        from tenant_platform.security.provider_keys import decrypt_provider_keys

        db = get_firestore()
        encrypted = get_provider_keys(db, channel_id)
        if not encrypted.get("pexels_api_key"):
            import logging
            logging.getLogger(__name__).error(
                f"No pexels_api_key found in Firestore for channel_id={channel_id!r}. "
                f"Stored fields present: {list(encrypted.keys())!r}"
            )
            return None
        return decrypt_provider_keys(encrypted)["pexels_api_key"]
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).error(
            f"Pexels key lookup/decrypt failed for channel_id={channel_id!r}: {e!r}"
        )
        return None


def _split_script_into_segments(script: str, count: int) -> list[str]:
    sentences = [s.strip() for s in _re.split(r"(?<=[.!?])\s+", script) if s.strip()]
    if not sentences:
        return [script] * count
    if len(sentences) <= count:
        return sentences + [sentences[-1]] * (count - len(sentences))
    step = len(sentences) / count
    return [sentences[int(i * step)] for i in range(count)]


def _query_from_segment(segment: str, fallback: str) -> str:
    words = [w.strip(".,!?\"'").lower() for w in segment.split()]
    words = [w for w in words if w and w not in _STOPWORDS]
    query = " ".join(words[:5])
    return query or fallback


@celery_app.task(
    name="workers.fetch_clips",
    autoretry_for=(requests.RequestException,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def fetch_clips(payload: dict[str, Any]) -> dict[str, Any]:
    channel_id = payload["channel_id"]
    run_id = payload["run_id"]
    script = payload.get("script") or ""
    channel_config = payload.get("channel_config", {})
    fallback_query = channel_config.get("category", "technology")

    api_key = _channel_pexels_key(channel_id) or os.environ.get("PEXELS_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No Pexels API key available: neither a channel-specific key "
            "nor PEXELS_API_KEY is set."
        )

    segments = _split_script_into_segments(script, CLIP_COUNT)
    out_dir = run_dir(channel_id, run_id)
    headers = {"Authorization": api_key}

    clip_paths: list[str] = []
    for i, segment in enumerate(segments):
        query = _query_from_segment(segment, fallback_query)
        resp = requests.get(
            PEXELS_SEARCH_URL,
            headers=headers,
            params={"query": query, "per_page": PER_PAGE, "orientation": "portrait"},
            timeout=30,
        )
        resp.raise_for_status()
        results = resp.json().get("videos", [])
        if not results:
            resp = requests.get(
                PEXELS_SEARCH_URL,
                headers=headers,
                params={"query": fallback_query, "per_page": PER_PAGE, "orientation": "portrait"},
                timeout=30,
            )
            resp.raise_for_status()
            results = resp.json().get("videos", [])
        if not results:
            continue

        video_files = results[0].get("video_files", [])
        portrait_files = [f for f in video_files if f.get("height", 0) > f.get("width", 0)]
        candidates = portrait_files or video_files
        candidates.sort(key=lambda f: f.get("width", 0))
        best = next((f for f in candidates if f.get("width", 0) <= 1080), candidates[-1] if candidates else None)
        if not best:
            continue

        clip_path = out_dir / f"clip_{i}.mp4"
        with requests.get(best["link"], stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(clip_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
        clip_paths.append(str(clip_path))

    if not clip_paths:
        raise RuntimeError("No background clips could be fetched from Pexels for this run.")

    return {**payload, "clip_paths": clip_paths}
