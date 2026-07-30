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

from ai.memory.clip_memory import get_used_clip_ids, record_clip_usage
from app.workers.celery_app import celery_app
from app.workers.storage import run_dir

PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"
CLIP_COUNT = 4
# Over-fetch candidates per query (was 1) so there's room to skip clips
# this channel already used for a similar topic — see clip_memory.py.
PER_PAGE = 15

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


def _select_best_file(video_files: list[dict]) -> dict | None:
    portrait_files = [f for f in video_files if f.get("height", 0) > f.get("width", 0)]
    candidates = portrait_files or video_files
    if not candidates:
        return None
    candidates.sort(key=lambda f: f.get("width", 0))
    return next((f for f in candidates if f.get("width", 0) <= 1080), candidates[-1])


def _pick_unused_video(results: list[dict], excluded_ids: set[str]) -> dict | None:
    """First video in `results` whose Pexels id isn't in `excluded_ids`
    (this channel's recent picks for a similar topic — see
    ai.memory.clip_memory). `results` is a ranked list from Pexels, so
    the first unused one is also the best-ranked unused one.
    """
    return next((v for v in results if str(v.get("id")) not in excluded_ids), None)


def _safe_get_used_clip_ids(channel_id: str, query: str) -> set[str]:
    """Wraps clip_memory.get_used_clip_ids: a Qdrant hiccup should mean
    "no exclusions this run", not a failed clip fetch — repeating a clip
    occasionally is far cheaper than breaking the run over it.
    """
    try:
        return get_used_clip_ids(channel_id, query)
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning(
            f"clip_memory lookup failed for channel_id={channel_id!r}, query={query!r}: {e!r}"
        )
        return set()


def _safe_record_clip_usage(channel_id: str, query: str, video_id: Any, clip_url: str) -> None:
    """Wraps clip_memory.record_clip_usage the same way — a failed write
    just means this pick won't be remembered next time, not a broken run."""
    try:
        record_clip_usage(channel_id, query, video_id=str(video_id), clip_url=clip_url)
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning(
            f"clip_memory write failed for channel_id={channel_id!r}, video_id={video_id!r}: {e!r}"
        )


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
        used_ids = _safe_get_used_clip_ids(channel_id, query)

        resp = requests.get(
            PEXELS_SEARCH_URL,
            headers=headers,
            params={"query": query, "per_page": PER_PAGE, "orientation": "portrait"},
            timeout=30,
        )
        resp.raise_for_status()
        results = resp.json().get("videos", [])

        video = _pick_unused_video(results, used_ids)
        if video is None:
            resp = requests.get(
                PEXELS_SEARCH_URL,
                headers=headers,
                params={"query": fallback_query, "per_page": PER_PAGE, "orientation": "portrait"},
                timeout=30,
            )
            resp.raise_for_status()
            fallback_results = resp.json().get("videos", [])
            video = _pick_unused_video(fallback_results, used_ids)
            results = fallback_results or results

        if video is None:
            # Every candidate we found for this topic has already been
            # used on this channel — reuse rather than fail the run.
            # This only happens once a channel has genuinely exhausted
            # the topically-relevant pool, not on a normal run.
            video = next(iter(results), None)
        if video is None:
            continue

        best = _select_best_file(video.get("video_files", []))
        if not best:
            continue

        clip_path = out_dir / f"clip_{i}.mp4"
        with requests.get(best["link"], stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(clip_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
        clip_paths.append(str(clip_path))

        video_id = video.get("id")
        if video_id is not None:
            _safe_record_clip_usage(channel_id, query, video_id=video_id, clip_url=best["link"])

    if not clip_paths:
        raise RuntimeError("No background clips could be fetched from Pexels for this run.")

    return {**payload, "clip_paths": clip_paths}
