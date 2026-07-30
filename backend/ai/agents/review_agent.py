"""
Review Agent (Ch.08) — Grammar Check -> Fact Check -> Copyright Check ->
LLM Judge, in order. A failure at any stage routes state back to the
relevant single Parallel Generation agent (Ch.07), never all six.

Short-circuit behavior: checks run in order and stop at the first
failure — there's no value in running Fact Check against a script that
already failed Grammar. "In order" (Ch.08) is what makes this a gate,
not a scoreboard.

Retry cap (Ch.04): "A per-node retry counter caps re-execution at three
attempts before the run is marked failed and handed to the Alert Agent
(Ch.19) instead of looping forever." The Alert Agent doesn't exist until
Phase 10, so for now hitting the cap just marks status="failed" with a
reason, and the conditional edge routes to END instead of retrying again.

Test-only hook: if state["force_fail_agent"] is set and that agent
hasn't already been force-failed once, this node skips the real
Grammar/Fact/Copyright/Judge calls entirely and returns a deterministic
failure targeting that agent. This exists so the Definition of Done
("a forced Review failure demonstrably retries the correct single
agent") is testable without live LLM calls. Real traffic through
POST /channels/{id}/generate never sets this field.
"""

from __future__ import annotations

from typing import Any, Optional

from ai.agents._utils import parse_json_response
from ai.langgraph.state import MAX_RETRIES_PER_AGENT, PARALLEL_AGENT_NAMES
from ai.models.llm_client import call_llm, DEFAULT_MODELS
from ai.prompts.prompt_library import (
    copyright_check_prompt,
    fact_check_prompt,
    grammar_check_prompt,
    llm_judge_prompt,
)

# Grammar/Fact/Copyright all inspect the script (and description, for
# grammar/copyright) — a failure at any of these three always targets
# "script" for Phase 4's single-hardcoded-channel scope, since the script
# is the one artifact every other check reads. The LLM Judge is the only
# check that can name any of the six agents (see llm_judge_prompt).
_SCRIPT_LEVEL_CHECK_TARGET = "script"


def _run_check(prompt: str, user_content: str) -> dict[str, Any]:
    raw = call_llm(
        model=DEFAULT_MODELS["grammar_check"],  # same default model for all three gate checks
        system_prompt=prompt,
        user_prompt=user_content,
        json_mode=True,
    )
    return parse_json_response(raw)


def _run_llm_judge(state: dict[str, Any]) -> dict[str, Any]:
    channel_config = state["channel_config"]
    payload = (
        f"Planner instructions: {state['planner_json']}\n\n"
        f"Script: {state['script']}\n\n"
        f"SEO: {state['seo']}\n\n"
        f"Thumbnail brief: {state['thumbnail_brief']}\n\n"
        f"Hook: {state['hook']}\n\n"
        f"Tags: {state['tags']}\n\n"
        f"Description: {state['description']}"
    )
    raw = call_llm(
        model=DEFAULT_MODELS["llm_judge"],
        system_prompt=llm_judge_prompt(channel_config),
        user_prompt=payload,
        json_mode=True,
    )
    return parse_json_response(raw)


def _next_retry_target(state: dict[str, Any]) -> tuple[Optional[str], list[dict[str, Any]]]:
    """Runs the four gates in order. Returns (retry_target, findings) —
    retry_target is None if everything passed.
    """
    findings: list[dict[str, Any]] = []

    grammar = _run_check(
        grammar_check_prompt(state["channel_config"]),
        f"Script: {state['script']}\n\nDescription: {state['description']}",
    )
    findings.append({"check": "grammar", **grammar})
    if not grammar.get("pass", False):
        return _SCRIPT_LEVEL_CHECK_TARGET, findings

    fact = _run_check(
        fact_check_prompt(state["channel_config"]),
        f"Research summary: {state['research_summary']}\n\nScript: {state['script']}",
    )
    findings.append({"check": "fact", **fact})
    if not fact.get("pass", False):
        return _SCRIPT_LEVEL_CHECK_TARGET, findings

    copyright_ = _run_check(
        copyright_check_prompt(),
        f"Script: {state['script']}\n\nDescription: {state['description']}",
    )
    findings.append({"check": "copyright", **copyright_})
    if not copyright_.get("pass", False):
        return _SCRIPT_LEVEL_CHECK_TARGET, findings

    judge = _run_llm_judge(state)
    findings.append({"check": "llm_judge", **judge})
    if not judge.get("pass", False):
        target = judge.get("retry_target")
        if target not in PARALLEL_AGENT_NAMES:
            # Judge didn't name a valid agent — fall back to script rather
            # than crash the run on a malformed judge response.
            target = _SCRIPT_LEVEL_CHECK_TARGET
        return target, findings

    return None, findings


async def review_node(state: dict[str, Any]) -> dict[str, Any]:
    retry_counts = dict(state.get("retry_counts", {}))
    force_fail_agent = state.get("force_fail_agent")

    if force_fail_agent and retry_counts.get(force_fail_agent, 0) < 1:
        target = force_fail_agent
        findings = [
            {
                "check": "test_hook",
                "pass": False,
                "issues": [f"Forced failure for {target} (test-only hook)"],
            }
        ]
    else:
        target, findings = _next_retry_target(state)

    if target is None:
        return {
            "review_verdict": "pass",
            "review_findings": findings,
            "retry_target": None,
            "status": "reviewed",
            "run_log": ["ran:review(pass)"],
        }

    attempts_so_far = retry_counts.get(target, 0)
    if attempts_so_far >= MAX_RETRIES_PER_AGENT:
        return {
            "review_verdict": "fail",
            "review_findings": findings,
            "retry_target": None,
            "status": "failed",
            "failure_reason": f"{target} exceeded {MAX_RETRIES_PER_AGENT} retries",
            "run_log": ["ran:review(fail:cap_exceeded)"],
        }

    retry_counts[target] = attempts_so_far + 1
    return {
        "review_verdict": "fail",
        "review_findings": findings,
        "retry_target": target,
        "retry_counts": retry_counts,
        "status": "running",
        "run_log": [f"ran:review(fail:{target})"],
    }
