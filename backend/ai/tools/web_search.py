"""
Web search tool — thin wrapper around Serper.dev's Search API.

Ch.05 (Research Agent & RAG) says RAG/Qdrant retrieval is deferred to
Phase 5 and Phase 4 should use "plain web search for now" to ground the
Research Agent's summary in current information instead of just asking
an LLM to recall it from training data.

This lives in backend/ai/tools/ (not backend/integrations/) per that
folder's README: a tool here is a thin wrapper around an integration,
shaped for what an agent needs — a list of (title, snippet, link) results
for a query, not Serper's raw JSON schema.

Env var required: SERPER_API_KEY
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

SERPER_SEARCH_URL = "https://google.serper.dev/search"


@dataclass
class SearchResult:
    title: str
    snippet: str
    link: str


def web_search(query: str, num_results: int = 5, timeout: float = 10.0) -> list[SearchResult]:
    """Runs a general web search via Serper and returns the top results.

    Retries are handled by the caller (Research Agent, per Ch.05's "web
    search and embedding calls retry twice with exponential backoff"
    policy) — this function makes one attempt and raises on failure.
    """
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "SERPER_API_KEY is not set. Add it to .env to enable web search."
        )

    response = httpx.post(
        SERPER_SEARCH_URL,
        json={"q": query, "num": num_results},
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        timeout=timeout,
    )
    response.raise_for_status()
    body = response.json()

    results = []
    for item in body.get("organic", [])[:num_results]:
        results.append(
            SearchResult(
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                link=item.get("link", ""),
            )
        )
    return results
