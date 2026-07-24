"""
Small helpers shared across agents. Not a public agent itself — leading
underscore keeps it out of anyone's "which agent is this" mental list.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def parse_json_response(raw: str) -> Any:
    """LLMs asked for JSON sometimes still wrap it in ```json fences or add
    a stray sentence before/after. Strip that, then parse. Raises
    json.JSONDecodeError if what's left still isn't valid JSON — callers
    should let that propagate so a malformed response surfaces as a real
    failure, not a silently wrong default.
    """
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    return json.loads(text)


def retry_skip(state: dict, agent_name: str) -> bool:
    """True if this Parallel Generation agent should skip real (expensive)
    work this pass — i.e. a retry is in progress AND it targets a
    *different* agent. See graph.py's module docstring for why this
    exists: LangGraph's fan-in join re-invokes all six writer nodes on
    every pass (that's how the join stays satisfied), but only the agent
    actually named in `retry_target` should redo real generation work.
    Ch.08: "only the agent whose output failed re-runs."
    """
    retry_target = state.get("retry_target")
    return retry_target is not None and retry_target != agent_name


def retry_with_backoff(
    fn: Callable[[], T],
    attempts: int = 3,
    base_delay_seconds: float = 1.0,
) -> T:
    """Runs `fn`, retrying on any exception with exponential backoff.
    Matches Ch.05's stated policy: "Web search and embedding calls retry
    twice with exponential backoff before the node fails over" — i.e. 2
    retries (3 total attempts) by default.
    """
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — intentionally broad, see docstring
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(base_delay_seconds * (2**attempt))
    assert last_error is not None
    raise last_error
