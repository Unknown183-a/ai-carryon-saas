"""
Planner Agent (Ch.06) — the one node in the graph that makes decisions
rather than generates content. Its output JSON is the single contract
every Parallel Generation agent (Ch.07) reads from; none of them
re-derive audience or tone independently.
"""

from __future__ import annotations

from typing import Any

from ai.agents._utils import parse_json_response
from ai.models.llm_client import call_llm, DEFAULT_MODELS
from ai.prompts.prompt_library import planner_prompt

REQUIRED_PLANNER_KEYS = {
    "video_length_sec",
    "voice_profile",
    "thumbnail_style",
    "seo_angle",
    "audience",
    "branding",
}


async def planner_node(state: dict[str, Any]) -> dict[str, Any]:
    channel_config = state["channel_config"]
    topic = state["topic"]
    research_summary = state["research_summary"]

    raw = call_llm(
        model=DEFAULT_MODELS["planner"],
        system_prompt=planner_prompt(channel_config),
        user_prompt=f"Topic: {topic}\n\nResearch summary:\n{research_summary}",
        json_mode=True,
    )
    planner_json = parse_json_response(raw)

    missing = REQUIRED_PLANNER_KEYS - planner_json.keys()
    if missing:
        raise ValueError(f"Planner output missing required keys: {missing}")

    return {
        "planner_json": planner_json,
        "run_log": ["ran:planner"],
    }
