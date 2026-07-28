"""
Shared "run the pipeline for one channel" logic (Ch.03/Ch.15).

Extracted in Phase 8 out of `app/api/routers/channels.py`'s
`generate_video` handler, which was the only caller until now. Phase 8
adds a second caller — `app/api/routers/internal_scheduler.py`'s
`POST /internal/scheduler/run-due-channels` — that needs the exact same
LangGraph invocation and the exact same response shape, just triggered
by the Scheduler (Ch.16) instead of a human hitting the button. Keeping
this in one place means those two callers structurally cannot drift
apart from each other over time; PHASE.md's Phase 8 task list literally
requires this ("...calls Phase 6's generate endpoint for each") — the
HTTP route and this function are one and the same logic, just reached
two different ways.

This module intentionally does NOT do any permission checking itself —
`require_channel_access` (user path, Ch.12e) and `require_system_token`
(scheduler path, Ch.16) are both dependency-injection-stage checks that
already ran, in their respective routers, before this function is ever
called. By the time `run_generation` executes, the caller has already
been confirmed allowed to trigger this specific channel.
"""

from __future__ import annotations

import uuid
from typing import Any

from ai.langgraph.graph import get_graph
from ai.models.provider_key_context import gemini_key_override, groq_key_override
from app.database.firestore_collections import record_run
from tenant_platform.channels.brain import load_channel_brain


async def run_generation(
    channel_id: str,
    channel_doc: dict[str, Any],
    triggered_by_uid: str,
    db: Any = None,
) -> dict[str, Any]:
    """Runs the full Trend -> Research -> Planner -> Parallel(6) ->
    Review pipeline for one channel and returns the same response shape
    `POST /channels/{id}/generate` has returned since Phase 6/7.

    `triggered_by_uid` becomes `parent_uid` in the LangGraph state
    (Ch.04) — for a human-triggered run this is the caller's own
    Firebase uid; for a Scheduler-triggered run
    (`internal_scheduler.py`) it's the channel's `owner_uid`, since
    there's no human caller to attribute the run to, but the pipeline
    still needs *some* uid for anything downstream that logs/keys by it.

    Phase 11: `db` is optional (defaults to `None`) purely so every
    existing caller/test that constructs this function's arguments by
    hand doesn't break — passing it in wires up `record_run` so this
    run shows up on the Logs screen. If `db` is `None`, run logging is
    silently skipped (the pipeline itself still runs); it's on each
    caller (both real ones already do) to actually pass a Firestore
    client through.
    """
    brain = load_channel_brain(channel_doc)
    run_id = str(uuid.uuid4())

    initial_state = {
        "channel_id": channel_id,
        "parent_uid": triggered_by_uid,
        "run_id": run_id,
        "channel_config": brain.to_pipeline_config(),
    }

    gemini_token = None
    groq_token = None
    if db is not None:
        try:
            from app.database.firestore_collections import get_provider_keys
            from tenant_platform.security.provider_keys import decrypt_provider_keys

            encrypted = get_provider_keys(db, channel_id)
            decrypted = decrypt_provider_keys(encrypted) if encrypted else {}
            if decrypted.get("gemini_api_key"):
                gemini_token = gemini_key_override.set(decrypted["gemini_api_key"])
            if decrypted.get("groq_api_key"):
                groq_token = groq_key_override.set(decrypted["groq_api_key"])
        except Exception:  # noqa: BLE001
            pass

    graph = get_graph()
    try:
        final_state = await graph.ainvoke(initial_state)
    except Exception as exc:  # noqa: BLE001 — still record the attempt before re-raising
        if db is not None:
            record_run(
                db,
                channel_id,
                {
                    "run_id": run_id,
                    "triggered_by_uid": triggered_by_uid,
                    "status": "error",
                    "failure_reason": str(exc),
                    "run_log": ["error:unhandled_exception"],
                },
            )
        raise

    if gemini_token is not None:
        gemini_key_override.reset(gemini_token)
    if groq_token is not None:
        groq_key_override.reset(groq_token)

    result = {
        "run_id": final_state["run_id"],
        "status": final_state.get("status"),
        "topic": final_state.get("topic"),
        "script": final_state.get("script"),
        "seo": final_state.get("seo"),
        "thumbnail_brief": final_state.get("thumbnail_brief"),
        "hook": final_state.get("hook"),
        "tags": final_state.get("tags"),
        "description": final_state.get("description"),
        "review_verdict": final_state.get("review_verdict"),
        "review_findings": final_state.get("review_findings"),
        "failure_reason": final_state.get("failure_reason"),
        "render_task_id": final_state.get("render_task_id"),
        "render_status": final_state.get("render_status"),
        "run_log": final_state.get("run_log", []),
    }

    if db is not None:
        record_run(db, channel_id, {**result, "triggered_by_uid": triggered_by_uid})

    return result
