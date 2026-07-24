"""
LangGraph StateGraph — Trend -> Research -> Planner -> Parallel(6) ->
Review, with a conditional retry edge (Ch.04's fig 4.1).

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


def _route_after_review(state: dict) -> str:
    if state.get("review_verdict") == "pass":
        return END
    if state.get("status") == "failed":
        # Retry cap exceeded (review_agent.py already set retry_target=None
        # in this case) — nothing left to do but end the run as failed.
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

    # Conditional edge (Ch.04/Ch.08): pass -> END, fail -> retry_dispatch,
    # which fans back out to all six (see module docstring).
    graph.add_conditional_edges(
        "review",
        _route_after_review,
        {"retry_dispatch": "retry_dispatch", END: END},
    )
    for name in PARALLEL_AGENT_NAMES:
        graph.add_edge("retry_dispatch", name)

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
