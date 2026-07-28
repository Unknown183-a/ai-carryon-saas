"""
LangGraph StateGraph — Trend -> Research -> Planner -> Parallel(6) ->
Review, with a conditional retry edge (Ch.04's fig 4.1), terminating in
an async render/upload hand-off on a passing review (Ch.15, Phase 7).

A LangGraph implementation note that shaped this file's structure, worth
reading before touching the retry wiring:
--------------------------------------------------------------------------
LangGraph's multi-source edge — `add_edge([a, b, c], "join_node")` — is an
AND-join: `join_node` only fires once ALL of a, b, and c have completed in
the same superstep. That's exactly what Ch.07's fan-out/fan-in needs for
the FIRST pass through the six Parallel Generation agents.

But Ch.08's retry only wants to re-run ONE failing agent. If review's
conditional edge routed straight back to just that one agent (e.g.
"seo"), the AND-join watching all six would never re-arm — only "seo"
would fire, "script"/"thumbnail"/etc. wouldn't, so the join's condition
("all six fired this round") is never satisfied again and the graph
quietly stops advancing past review. This was verified with a minimal
prototype during Phase 4 planning; it's not a hypothetical.

The fix: on retry, route to `retry_dispatch`, which fans out to ALL SIX
writer nodes again (re-arming the AND-join) — but each writer node
checks `ai.agents._utils.retry_skip(state, its_own_name)` first and, if
it isn't the named retry target, returns instantly without calling an
LLM. So all six nodes "run" every retry pass (satisfying the join), but
only the failing one does real (expensive) work. This is verified by
tests/phase4_langgraph_test.py, which asserts the real-work call count
per agent, not just that the response looks right.
--------------------------------------------------------------------------

Phase 7 addition — `enqueue_render`: per Ch.15's fig 15.1
("fire-and-track, not fire-and-forget"), a passing review no longer ends
the run directly. It routes through one more node whose only job is to
hand the reviewed outputs to the Celery worker chain
(voice -> thumbnail -> render -> upload) and return immediately — see
that node's own docstring below for why the import is deliberately
local to the function, not at module scope. A failed run (retry cap
exceeded) still routes straight to END — there's nothing to render for
a script that never passed review.
"""

from __future__ import annotations

from langgraph.graph import StateGraph, END

from ai.agents.description_agent import description_node
from ai.agents.hook_agent import hook_node
from ai.agents.planner_agent import planner_node
from ai.agents.research_agent import research_node
from ai.agents.review_agent import review_node
from ai.agents.script_agent import script_node
from ai.agents.seo_agent import seo_node
from ai.agents.tags_agent import tags_node
from ai.agents.thumbnail_agent import thumbnail_node
from ai.agents.trend_agent import trend_node
from ai.langgraph.state import PARALLEL_AGENT_NAMES, PipelineState

_WRITER_NODES = {
    "script": script_node,
    "seo": seo_node,
    "thumbnail": thumbnail_node,
    "hook": hook_node,
    "tags": tags_node,
    "description": description_node,
}


async def _retry_dispatch(state: dict) -> dict:
    """No-op pass-through node — see the module docstring for why this
    exists: it's the re-entry point that re-arms the six-way AND-join
    without doing any work itself.
    """
    return {"run_log": ["ran:retry_dispatch"]}


async def _enqueue_render(state: dict) -> dict:
    """Terminal node (Ch.15, Phase 7): hands the reviewed outputs to the
    async worker chain (voice -> thumbnail -> render -> upload) instead
    of rendering/uploading on the request thread, and returns
    immediately — fig 15.1's "fire-and-track, not fire-and-forget", NOT
    "wait for the chain to finish before ending the graph run." A full
    render+upload can take minutes (Ch.15's own duration table);
    blocking `graph.ainvoke()` on that would silently reintroduce the
    exact problem this phase exists to remove, just one layer further
    in. `render_task_id` is returned so a caller (or a future status-
    polling endpoint / WS, Ch.03) can track the chain's progress
    separately from the pipeline run itself.

    The `app.workers.*` imports are deliberately LOCAL to this function,
    not at module top, for one concrete reason: every test in this
    project already imports `ai.langgraph.graph` (directly or via
    `app.api.routers.channels`), including Phase 4/5/6's suites, which
    have no interest in Celery or a Redis broker connection at all.
    Importing `app.workers.celery_app` at module scope would make
    `CELERY_BROKER_URL` a required env var just to BUILD the graph
    object, breaking every earlier phase's test for a dependency they
    never asked for. Only a run that actually reaches this node —
    i.e. one that passed review — needs the worker chain to be
    importable/configured at all.
    """
    from celery import chain

    from app.workers.clips_worker import fetch_clips
    from app.workers.finalize_worker import (
        finalize_render_failure,
        finalize_render_success,
    )
    from app.workers.render_worker import render_video
    from app.workers.thumbnail_worker import generate_thumbnail
    from app.workers.upload_worker import upload_to_youtube
    from app.workers.voice_worker import generate_voice

    channel_id = state["channel_id"]
    run_id = state["run_id"]
    channel_config = state.get("channel_config") or {}
    render_payload = {
        "channel_id": channel_id,
        "run_id": run_id,
        "channel_config": channel_config,
        "script": state.get("script"),
        "voice_profile": channel_config.get("voice_profile"),
        "thumbnail_brief": state.get("thumbnail_brief"),
        "seo": state.get("seo"),
        "tags": state.get("tags"),
        "description": state.get("description"),
    }

    render_chain = chain(
        generate_voice.s(render_payload),
        generate_thumbnail.s(),
        fetch_clips.s(),
        render_video.s(),
        upload_to_youtube.s(),
    )
    # Phase 12: close the "render_status: enqueued forever" gap — see
    # finalize_worker.py's module docstring for why these are wired as
    # link=/link_error= rather than plain chain steps, and why
    # channel_id/run_id are bound here rather than relied on to arrive
    # as call arguments.
    async_result = render_chain.apply_async(
        link=finalize_render_success.s(channel_id=channel_id, run_id=run_id),
        link_error=finalize_render_failure.s(channel_id=channel_id, run_id=run_id),
    )

    return {
        "render_task_id": async_result.id,
        "render_status": "enqueued",
        "run_log": ["ran:enqueue_render"],
    }


def _route_after_review(state: dict) -> str:
    if state.get("review_verdict") == "pass":
        return "enqueue_render"
    if state.get("status") == "failed":
        # Retry cap exceeded (review_agent.py already set retry_target=None
        # in this case) — nothing left to do but end the run as failed.
        # Nothing to render for a script that never passed review.
        return END
    return "retry_dispatch"


def build_graph():
    graph = StateGraph(PipelineState)

    graph.add_node("trend", trend_node)
    graph.add_node("research", research_node)
    graph.add_node("planner", planner_node)
    for name, node_fn in _WRITER_NODES.items():
        graph.add_node(name, node_fn)
    graph.add_node("review", review_node)
    graph.add_node("retry_dispatch", _retry_dispatch)
    graph.add_node("enqueue_render", _enqueue_render)

    # Sequential prefix (Ch.04: "Trend -> Research -> Planner run strictly
    # in order; each depends on the previous node's output.")
    graph.set_entry_point("trend")
    graph.add_edge("trend", "research")
    graph.add_edge("research", "planner")

    # Fan-out: planner triggers all six writers independently (Ch.07).
    for name in PARALLEL_AGENT_NAMES:
        graph.add_edge("planner", name)

    # Fan-in: review only fires once all six have completed this round.
    graph.add_edge(list(PARALLEL_AGENT_NAMES), "review")

    # Conditional edge (Ch.04/Ch.08/Ch.15): pass -> enqueue_render -> END,
    # fail (cap exceeded) -> END directly, retry -> retry_dispatch, which
    # fans back out to all six (see module docstring).
    graph.add_conditional_edges(
        "review",
        _route_after_review,
        {"retry_dispatch": "retry_dispatch", "enqueue_render": "enqueue_render", END: END},
    )
    for name in PARALLEL_AGENT_NAMES:
        graph.add_edge("retry_dispatch", name)
    graph.add_edge("enqueue_render", END)

    return graph.compile()


# Compiled once per process, same pattern as backend/app/core/redis_client.py's
# lazy singleton — building the graph has a small fixed cost, no reason to
# repeat it per request.
_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph
