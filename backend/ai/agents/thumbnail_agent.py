"""Thumbnail Agent — one of the six Parallel Generation agents (Ch.07).

Produces a thumbnail *brief* (headline text, visual concept, style) —
per this phase's scope, no image is rendered yet. That's the render
pipeline, out of scope until later phases.
"""

from __future__ import annotations

from typing import Any

from ai.agents._utils import parse_json_response, retry_skip
from ai.models.llm_client import call_llm, DEFAULT_MODELS
from ai.prompts.prompt_library import thumbnail_prompt

AGENT_NAME = "thumbnail"


async def thumbnail_node(state: dict[str, Any]) -> dict[str, Any]:
    if retry_skip(state, AGENT_NAME):
        return {"run_log": [f"skipped:{AGENT_NAME}"]}

    channel_config = state["channel_config"]
    research_summary = state["research_summary"]
    planner_json = state["planner_json"]

    raw = call_llm(
        model=DEFAULT_MODELS["thumbnail"],
        system_prompt=thumbnail_prompt(channel_config),
        user_prompt=(
            f"Research summary:\n{research_summary}\n\n"
            f"Planner instructions:\n{planner_json}"
        ),
        json_mode=True,
    )
    thumbnail_brief = parse_json_response(raw)

    return {"thumbnail_brief": thumbnail_brief, "run_log": [f"ran:{AGENT_NAME}"]}
