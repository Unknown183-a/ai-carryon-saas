"""
Finalize Worker (Phase 12).

Closes the gap flagged against `graph.py`'s `_enqueue_render`: that node
writes `render_status: "enqueued"` to the run doc exactly once and never
touches it again, because "chain progress itself lives in Celery's own
result backend, not here." True, but it left the Logs screen unable to
ever show a finished render as finished — every run just sat on
"enqueued" forever, whether the video shipped in 90 seconds or the
worker died on step one.

These two tasks are wired on as `link=`/`link_error=` on the render
chain's `apply_async()` call in `graph.py`, NOT as literal chain steps —
that distinction matters:

  - A literal `chain(...)` step only runs if every prior step succeeded.
    A crash in `render_video` would mean `upload_to_youtube` never runs,
    and a trailing "finalize" step chained after it wouldn't run either
    — leaving the run stuck on "enqueued" exactly as before, just with
    extra code that never fires.
  - `link=` fires only on success, with the chain's final return value
    (upload_to_youtube's payload dict) as its first argument.
  - `link_error=` fires on failure from ANY step in the chain, but per
    Celery's own calling convention for error callbacks, it receives
    only the failed task's id, not the payload — which is exactly why
    `channel_id`/`run_id` are bound onto both signatures via `.s(...)`
    at chain-construction time in `graph.py`, rather than relied on to
    arrive as call arguments.
"""

from __future__ import annotations

from typing import Any

from app.workers.celery_app import celery_app


@celery_app.task(name="workers.finalize_render_success")
def finalize_render_success(
    result: dict[str, Any], channel_id: str, run_id: str
) -> dict[str, Any]:
    # Best-effort, like upload_worker.py's `_channel_youtube_token`: the
    # video already shipped by the time this runs (it's the success
    # callback) — a Firestore hiccup here should never look like the
    # render itself failed, so this never raises. Same reasoning is why
    # `link=` callbacks in Celery run outside the chain's own retry
    # machinery — this being best-effort rather than retried is a
    # deliberate match to that, not an oversight.
    try:
        from app.api.dependencies import get_firestore
        from app.database.firestore_collections import update_run_status

        db = get_firestore()
        update_run_status(
            db,
            run_id,
            {
                "render_status": "completed",
                "youtube_video_id": result.get("youtube_video_id"),
            },
        )
    except Exception:  # noqa: BLE001
        pass
    return result


@celery_app.task(name="workers.finalize_render_failure")
def finalize_render_failure(
    failed_task_id: str, channel_id: str, run_id: str
) -> None:
    # Pull the actual exception text off the failed task's own
    # AsyncResult for a useful failure_reason — wrapped separately from
    # the Firestore write below because a result-backend lookup failing
    # shouldn't stop this task from still attempting to mark the run
    # "failed" with a generic reason.
    reason = f"render chain task {failed_task_id} failed"
    try:
        failed_result = celery_app.AsyncResult(failed_task_id)
        if failed_result.result is not None:
            reason = str(failed_result.result)
    except Exception:  # noqa: BLE001
        pass

    # Best-effort, same reasoning as finalize_render_success: a Firestore
    # write failing here shouldn't raise and mask the real render
    # failure this task exists to record.
    try:
        from app.api.dependencies import get_firestore
        from app.database.firestore_collections import update_run_status

        db = get_firestore()
        update_run_status(
            db,
            run_id,
            {
                "render_status": "failed",
                "render_failure_reason": reason,
            },
        )
    except Exception:  # noqa: BLE001
        pass
