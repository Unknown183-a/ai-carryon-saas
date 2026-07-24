"""
Channel long-term memory (per this folder's README: "lessons_learned
retrieval, prior-run memory... empty until Phase 5 wires the first
retrieval call").

This is a thin, named facade over `ai.rag.retriever.hybrid_search`
scoped to the two collections that represent a channel's accumulated
memory rather than this-run's grounding data: `lessons_learned` (Ch.20's
Learning Agent writes here — doesn't exist until Phase 12, so this
returns an empty list on every real call until then) and
`prompt_history` (which prompts worked, for future use).

Why this exists as its own module instead of agents calling
`hybrid_search("lessons_learned", ...)` directly: it gives future
callers (Phase 12's Learning Agent, and any other agent that wants past
lessons) one obvious place to ask "what do we already know about this
channel/topic" without needing to know Qdrant collection names or the
hybrid-search signature — same reasoning as ai/models/ sitting on top of
integrations/.
"""

from __future__ import annotations

from ai.rag.retriever import RetrievedChunk, hybrid_search


def get_lessons_learned(channel_id: str, topic: str, limit: int = 3) -> list[RetrievedChunk]:
    """Past distilled patterns (Ch.20) relevant to `topic`, for this
    channel. Returns an empty list, not an error, when nothing has been
    written yet — expected for every channel until Phase 12's Learning
    Agent exists and has run at least once.
    """
    return hybrid_search(topic, collection="lessons_learned", channel_id=channel_id, limit=limit)
