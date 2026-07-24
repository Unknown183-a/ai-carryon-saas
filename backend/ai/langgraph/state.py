"""
Shared state schema for the LangGraph pipeline (Ch.04).

LangGraph threads one mutable state object through every node. Every
field an agent reads or writes lives here. Per Ch.03 ("How FastAPI talks
to LangGraph"), the router only ever constructs the initial dict with
channel_id / parent_uid / run_id — everything else gets filled in as the
graph runs.

Concurrency note: the six Parallel Generation agents (Ch.07) run in the
same LangGraph superstep and each writes to its OWN key (script, seo_json,
etc.) — no two of them ever write the same key in the same step, so plain
(non-reducer) fields are safe. `run_log` is the one field multiple nodes
can append to concurrently, so it needs an `Annotated[..., operator.add]`
reducer or LangGraph raises InvalidUpdateError — see graph.py's retry
fan-out for exactly when that happens.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Optional, TypedDict

# The six Parallel Generation agents from Ch.07 — used by graph.py to wire
# the fan-out/fan-in edges and by review_agent.py to validate a retry
# target is one of these.
PARALLEL_AGENT_NAMES = ["script", "seo", "thumbnail", "hook", "tags", "description"]

MAX_RETRIES_PER_AGENT = 3


class PipelineState(TypedDict, total=False):
    # ── Set by FastAPI before graph.ainvoke() (Ch.03) ──────────────────
    channel_id: str
    parent_uid: str
    run_id: str

    # ── Channel identity (Phase 4: hardcoded; Phase 6: from Firestore) ─
    channel_config: dict[str, Any]

    # ── Trend node output (Ch.04 node table) ───────────────────────────
    topic: str
    trend_candidates: list[str]

    # ── Research node output (Ch.05) ───────────────────────────────────
    research_summary: str
    research_sources: list[str]

    # ── Planner node output — the Ch.06 JSON contract ──────────────────
    planner_json: dict[str, Any]

    # ── Parallel Generation outputs (Ch.07), one key per agent ─────────
    script: str
    seo: dict[str, Any]
    thumbnail_brief: dict[str, Any]
    hook: str
    tags: list[str]
    description: str

    # ── Review layer (Ch.08) ───────────────────────────────────────────
    review_verdict: str  # "pass" | "fail"
    review_findings: list[dict[str, Any]]  # one entry per check that ran
    retry_target: Optional[str]  # which single Parallel agent to re-run, or None
    retry_counts: dict[str, int]  # per-agent retry counter, capped at MAX_RETRIES_PER_AGENT

    # ── Test-only hook (Definition of Done: prove single-agent retry) ──
    # When set, review_agent.py forces exactly one failure against this
    # agent on its first pass, so a test can assert only that agent
    # re-ran. Never set by real traffic — FastAPI's /generate endpoint
    # never populates this field itself.
    force_fail_agent: Optional[str]

    # ── Terminal status ─────────────────────────────────────────────────
    status: str  # "running" | "reviewed" | "failed"
    failure_reason: Optional[str]

    # ── Shared accumulating log (needs a reducer — see module docstring) ─
    run_log: Annotated[list[str], operator.add]
