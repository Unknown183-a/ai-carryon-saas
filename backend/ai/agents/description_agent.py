"""Description Agent — one of the six Parallel Generation agents (Ch.07)."""

from __future__ import annotations

from typing import Any

from ai.agents._utils import retry_skip
from ai.models.llm_client import call_llm, DEFAULT_MODELS
from ai.prompts.prompt_library import description_prompt

AGENT_NAME = "description"


async def description_node(state: dict[str, Any]) -> dict[str, Any]:
    if retry_skip(state, AGENT_NAME):
        return {"run_log": [f"skipped:{AGENT_NAME}"]}

    channel_config = state["channel_config"]
    research_summary = state["research_summary"]
    planner_json = state["planner_json"]

    description = call_llm(
        model=DEFAULT_MODELS["description"],
        system_prompt=description_prompt(channel_config),
        user_prompt=(
            f"Research summary:\n{research_summary}\n\n"
            f"Planner instructions:\n{planner_json}"
        ),
    )

    return {"description": description.strip(), "run_log": [f"ran:{AGENT_NAME}"]}
