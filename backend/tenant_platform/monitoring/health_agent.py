"""
Health Agent (Ch.18, Phase 10) — a small LangGraph that fans out to one
check node per dependency (Redis, Firestore, Qdrant, Celery workers,
Scheduler staleness, YouTube API, LLM providers), then joins into a
single aggregate result. Same fan-out/AND-join shape `ai/langgraph/graph.py`
already uses for the six Parallel Generation agents — see that file's
module docstring for why an AND-join is the right tool here too: every
check node should run every poll regardless of whether an earlier one
already failed, since one dependency being down says nothing about
whether the others are also down.

This graph does NOT decide what to do about a failing check — that's
`alert_agent.py`'s job (retry-then-escalate policy, Ch.19). This module
only answers "what's the state of the world right now", nothing more.

Called from `app/api/routers/internal_health.py`, itself triggered on a
timer the same way `internal_scheduler.py` is (Ch.16 mechanism, reused
per this phase's task list) — a Cloud Scheduler job (or cron, until/if
that's ever needed) hitting a `require_system_token`-guarded endpoint,
not anything Redis/Qdrant/etc. push to this app on their own.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.core.qdrant_client import get_qdrant
from app.core.redis_client import get_redis
from app.database.firestore_collections import list_enabled_schedules
from integrations.youtube.client import check_connection as youtube_check_connection


class HealthCheckState(TypedDict, total=False):
    db: Any  # Firestore Client, passed through, never itself checked for JSON-serializability — this graph is invoked once and discarded, no checkpointer
    services: Annotated[list[dict[str, Any]], operator.add]
    overall_ok: bool


def _result(service: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"service": service, "ok": ok, "detail": detail}


def check_redis(state: HealthCheckState) -> dict[str, Any]:
    try:
        redis = get_redis()
        probe_key = "health_agent:probe"
        redis.set(probe_key, "ok", ex=30)
        value = redis.get(probe_key)
        redis.delete(probe_key)
        ok = value == "ok"
        return {"services": [_result("redis", ok, "set/get round-trip" if ok else f"unexpected value: {value!r}")]}
    except Exception as exc:  # noqa: BLE001 — one check's failure must not sink the whole poll
        return {"services": [_result("redis", False, f"{type(exc).__name__}: {exc}")]}


def check_firestore(state: HealthCheckState) -> dict[str, Any]:
    try:
        # Cheapest possible real read: list up to 1 doc from a
        # collection guaranteed to exist in any live deployment
        # (schedules gets a doc the moment the first channel is
        # created — Phase 6's Channel Factory). An empty result is
        # still a successful read, not a failure — this proves
        # Firestore answered, not that any particular data exists.
        list(state["db"].collection("schedules").limit(1).stream())
        return {"services": [_result("firestore", True, "read succeeded")]}
    except Exception as exc:  # noqa: BLE001
        return {"services": [_result("firestore", False, f"{type(exc).__name__}: {exc}")]}


def check_qdrant(state: HealthCheckState) -> dict[str, Any]:
    try:
        qdrant = get_qdrant()
        exists = qdrant.collection_exists("research")
        return {"services": [_result("qdrant", True, f"reachable, 'research' collection exists: {exists}")]}
    except Exception as exc:  # noqa: BLE001
        return {"services": [_result("qdrant", False, f"{type(exc).__name__}: {exc}")]}


def check_workers(state: HealthCheckState) -> dict[str, Any]:
    """Celery's own `control.inspect().ping()` — asks every connected
    worker to respond over the broker, distinct from
    `worker_entrypoint.py`'s $PORT health check (Phase 9), which only
    proves the Cloud Run container is alive, not that Celery inside it
    is actually consuming tasks. This is the check that closes that gap.
    """
    try:
        from app.workers.celery_app import celery_app  # local: see this module's import comment above graph.py's _enqueue_render for why

        replies = celery_app.control.inspect(timeout=5.0).ping()
        ok = bool(replies)
        detail = f"{len(replies or {})} worker(s) responded" if ok else "no worker responded to ping"
        return {"services": [_result("workers", ok, detail)]}
    except Exception as exc:  # noqa: BLE001
        return {"services": [_result("workers", False, f"{type(exc).__name__}: {exc}")]}


def check_scheduler(state: HealthCheckState) -> dict[str, Any]:
    """Not "is the Scheduler mechanism itself up" (this endpoint being
    invoked at all already proves that) — this checks whether any
    enabled channel's schedule has gone stale, i.e. `next_run_at` is
    long past with no `last_run_at` catching up to it, which would mean
    the Scheduler's cron/Cloud Scheduler job itself stopped firing
    upstream of this app entirely (nothing inside this app would ever
    notice that on its own, since a poll that never happens can't report
    its own absence).
    """
    import datetime

    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        stale = []
        for schedule in list_enabled_schedules(state["db"]):
            next_run_at = schedule.get("next_run_at")
            if not next_run_at:
                continue
            next_run_dt = datetime.datetime.fromisoformat(next_run_at)
            overdue = now - next_run_dt
            if overdue > datetime.timedelta(hours=1):
                stale.append(schedule["channel_id"])
        ok = not stale
        detail = "no schedule overdue by more than 1h" if ok else f"overdue: {stale}"
        return {"services": [_result("scheduler", ok, detail)]}
    except Exception as exc:  # noqa: BLE001
        return {"services": [_result("scheduler", False, f"{type(exc).__name__}: {exc}")]}


def check_youtube(state: HealthCheckState) -> dict[str, Any]:
    result = youtube_check_connection()
    return {"services": [_result("youtube", result["ok"], result["detail"])]}


def check_llm_providers(state: HealthCheckState) -> dict[str, Any]:
    """Deliberately checks env-var presence only, not a live generate()
    call — a live call against Gemini/Groq/OpenAI every 5 minutes has a
    real dollar cost for a check that mostly wants to catch "someone
    revoked/rotated a key and forgot to update Secret Manager", which a
    presence check already catches for the "forgot entirely" case. A key
    that's present but invalid/expired will surface the first time a
    real generation run tries to use it (and THAT failure has its own
    retry-then-escalate path through render/generation failures, not
    this one) — an acceptable gap given the cost trade-off.
    """
    import os

    missing = [
        var
        for var in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY")
        if not os.environ.get(var)
    ]
    ok = not missing
    detail = "all 3 provider keys present" if ok else f"missing: {missing}"
    return {"services": [_result("llm_providers", ok, detail)]}


def aggregate(state: HealthCheckState) -> dict[str, Any]:
    services = state.get("services", [])
    return {"overall_ok": all(s["ok"] for s in services)}


def build_graph():
    graph = StateGraph(HealthCheckState)

    check_nodes = [
        ("check_redis", check_redis),
        ("check_firestore", check_firestore),
        ("check_qdrant", check_qdrant),
        ("check_workers", check_workers),
        ("check_scheduler", check_scheduler),
        ("check_youtube", check_youtube),
        ("check_llm_providers", check_llm_providers),
    ]
    for name, fn in check_nodes:
        graph.add_node(name, fn)
        graph.add_edge(START, name)

    graph.add_node("aggregate", aggregate)
    graph.add_edge([name for name, _ in check_nodes], "aggregate")
    graph.add_edge("aggregate", END)

    return graph.compile()


_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


async def run_health_check(db: Any) -> dict[str, Any]:
    """Entry point for `internal_health.py`. Returns
    `{"overall_ok": bool, "services": [{"service", "ok", "detail"}, ...]}`.
    """
    graph = _get_graph()
    result = await graph.ainvoke({"db": db, "services": []})
    return {"overall_ok": result["overall_ok"], "services": result["services"]}
