"""
Clip Agent's usage memory: which Pexels background clips a channel has
already used, so `app/workers/clips_worker.py` can avoid picking the
same clip again for the same channel.

Same facade pattern as `channel_memory.py` in this folder: a thin,
named wrapper over `ai.rag.retriever` scoped to one collection
(`clip_history`), so the worker doesn't need to know Qdrant collection
names or the hybrid-search signature.

Isolation note (why this is RAG and not a global "used video IDs" set):
every read and write here goes through `channel_id`, exactly like every
other collection in `ai/rag/collections.py` — Ch.12e's mandatory
channel_id filter (`channel_filter()` in `app/core/qdrant_client.py`)
is what keeps one channel's clip history from leaking into another's
picks. Two channels covering the same topic build entirely separate
clip-history entries and never influence each other's selection —
that's the isolation the retriever module already enforces for every
other collection, applied here too.

`get_used_clip_ids` retrieves by semantic similarity to the current
topic/segment rather than returning a channel's *entire* history. This
is deliberate: a channel that's made hundreds of videos shouldn't
permanently exile a clip from ever being reused once the topic drifts
far enough away — only clips used for topically similar segments count
as "recent repeats" worth avoiding. `clips_worker.py` also over-fetches
candidates from Pexels per query, so even a full miss here (cold
channel, brand-new topic) just means no exclusions apply, not a
failure.
"""

from __future__ import annotations

from ai.rag.retriever import hybrid_search, store_chunks

CLIP_HISTORY_COLLECTION = "clip_history"

# How many past similar-topic clip usages to pull back per query before
# excluding their video IDs. Kept small and topic-scoped on purpose —
# see module docstring on why this isn't "every clip ever used".
DEFAULT_LOOKBACK = 12


def get_used_clip_ids(channel_id: str, topic: str, limit: int = DEFAULT_LOOKBACK) -> set[str]:
    """Returns the set of Pexels video IDs (as strings) this channel has
    already used for segments topically similar to `topic`. Returns an
    empty set, not an error, when nothing has been recorded yet — the
    normal state for a channel's first run or a brand-new topic.
    """
    chunks = hybrid_search(topic, collection=CLIP_HISTORY_COLLECTION, channel_id=channel_id, limit=limit)
    return {
        str(chunk.metadata["video_id"])
        for chunk in chunks
        if chunk.metadata.get("video_id") is not None
    }


def record_clip_usage(channel_id: str, topic: str, video_id: str, clip_url: str) -> None:
    """Records that `video_id` was picked for `topic` on this channel, so
    a future run with a similar topic on the *same* channel can exclude
    it. `topic` is stored as the searchable text (what future queries
    match against); `video_id`/`clip_url` ride along as metadata.
    """
    store_chunks(
        CLIP_HISTORY_COLLECTION,
        topic,
        metadata={"channel_id": channel_id, "video_id": str(video_id), "clip_url": clip_url},
    )
