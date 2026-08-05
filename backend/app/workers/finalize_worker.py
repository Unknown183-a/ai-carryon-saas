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
def finalize_render_failure(*args: object, channel_id: str, run_id: str) -> None:
    """`channel_id`/`run_id` are keyword-only and `*args` absorbs
    whatever Celery hands this errback positionally — deliberately,
    after a real failure proved the previous fixed-arity signature
    wrong. `finalize_worker.py`'s module docstring's claim that
    `link_error=` "receives only the failed task's id" holds for a
    real broker redelivery, but `backends/base.py`'s
    `_call_task_errbacks` (the path a `task_always_eager`/in-process
    failure — or, it turns out, a real worker's own local failure
    handling — actually goes through) calls `errback(request, exc,
    traceback)`: three positional args, not one. Against the old
    `(failed_task_id, channel_id, run_id)` signature, the second
    positional arg landed in `channel_id`'s slot at the same time
    `channel_id=` arrived as a keyword — `TypeError: ... got multiple
    values for argument 'channel_id'`, silently swallowing every real
    render failure this task exists to record. Absorbing everything
    positional into `*args` makes this signature agnostic to which of
    Celery's error-callback calling conventions actually fires.
    """
    # The failed task's id may show up as a bare string (a real
    # broker's redelivery path) or as a `Context`/`Request`-like object
    # with an `.id` attribute (the `_call_task_errbacks` path above) —
    # take whichever positional arg actually looks like an id instead
    # of assuming position 0 is always it.
    failed_task_id: str | None = None
    for arg in args:
        if isinstance(arg, str):
            failed_task_id = arg
            break
        candidate = getattr(arg, "id", None)
        if isinstance(candidate, str):
            failed_task_id = candidate
            break

    # Pull the actual exception text off the failed task's own
    # AsyncResult for a useful failure_reason — wrapped separately from
    # the Firestore write below because a result-backend lookup failing
    # shouldn't stop this task from still attempting to mark the run
    # "failed" with a generic reason. Also fall back to an `exc` object
    # passed directly in `*args` (the `_call_task_errbacks` path always
    # includes one) when there's no task id to look up by.
    reason = f"render chain task {failed_task_id} failed" if failed_task_id else "render chain task failed"
    try:
        if failed_task_id:
            failed_result = celery_app.AsyncResult(failed_task_id)
            if failed_result.result is not None:
                reason = str(failed_result.result)
        else:
            exc = next((a for a in args if isinstance(a, BaseException)), None)
            if exc is not None:
                reason = str(exc)
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
