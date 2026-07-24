"""
Script Agent — one of the six Parallel Generation agents (Ch.07). Reads
only the research summary and the Planner's JSON; never calls another
Parallel agent, which is what makes running all six concurrently safe.

See ai/agents/_utils.py:retry_skip for why this node still executes on
every retry pass but only does real work when it's the retry target.
"""

from __future__ import annotations

from typing import Any

from ai.agents._utils import retry_skip
from ai.models.llm_client import call_llm, DEFAULT_MODELS
from ai.prompts.prompt_library import script_prompt

AGENT_NAME = "script"


async def script_node(state: dict[str, Any]) -> dict[str, Any]:
    if retry_skip(state, AGENT_NAME):
        return {"run_log": [f"skipped:{AGENT_NAME}"]}

    channel_config = state["channel_config"]
    research_summary = state["research_summary"]
    planner_json = state["planner_json"]

    script = call_llm(
        model=DEFAULT_MODELS["script"],
        system_prompt=script_prompt(channel_config),
        user_prompt=(
            f"Research summary:\n{research_summary}\n\n"
            f"Planner instructions:\n{planner_json}"
        ),
    )

    return {"script": script.strip(), "run_log": [f"ran:{AGENT_NAME}"]}
