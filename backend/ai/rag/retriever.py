"""
Retriever (Ch.09): hybrid search over a Qdrant collection — vector
similarity combined with a keyword-overlap score, always filtered to one
channel first (Ch.09: "so retrieval can filter... before it ranks by
similarity, rather than searching the entire vector space"; Ch.12e:
every Qdrant query carries a mandatory channel_id filter).

Also owns `store_chunks()` — the write side of the same pipeline
(chunk -> embed -> upsert), used by research_agent.py to write each new
research summary back into the `research` collection, and by
rag/backfill.py to seed history from the old pipeline. Chunking,
embedding, and retrieval all meet here because storing and searching a
collection need to agree on the same chunk/embedding shape.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.qdrant_client import channel_filter, get_qdrant
from ai.rag.chunker import chunk_text
from ai.rag.embed import embed_text

# Weight given to vector similarity vs. keyword overlap in the combined
# score (Ch.09: "combines vector similarity with a keyword-overlap
# score, so an exact term match can outrank a vaguer semantic neighbor
# when both signals matter"). Vector similarity carries most of the
# weight since it's the stronger general-purpose signal; keyword overlap
# is the tie-breaker/override for exact-term relevance.
VECTOR_WEIGHT = 0.7
KEYWORD_WEIGHT = 0.3

# How many candidates to pull from Qdrant's vector search before
# re-ranking with keyword overlap and truncating to `limit`. Over-fetch
# so a chunk with a weaker vector score but a strong keyword match still
# has a chance to surface.
OVER_FETCH_MULTIPLIER = 4

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "he", "in", "is", "it", "its", "of", "on", "that", "the", "to", "was",
    "were", "will", "with", "this", "these", "those", "or", "but", "not",
}


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOPWORDS}


def _keyword_overlap_score(query_tokens: set[str], chunk_text_value: str) -> float:
    if not query_tokens:
        return 0.0
    chunk_tokens = _tokenize(chunk_text_value)
    overlap = query_tokens & chunk_tokens
    return len(overlap) / len(query_tokens)


@dataclass
class RetrievedChunk:
    text: str
    score: float
    vector_score: float
    keyword_score: float
    metadata: dict[str, Any] = field(default_factory=dict)


def hybrid_search(
    query: str,
    collection: str,
    channel_id: str,
    limit: int = 5,
    extra_filter: Optional[dict[str, Any]] = None,
) -> list[RetrievedChunk]:
    """Returns up to `limit` chunks from `collection`, filtered to
    `channel_id`, ranked by a blend of vector similarity and keyword
    overlap with `query`. Returns an empty list (not an error) if the
    collection has nothing for this channel yet — a cold Qdrant is a
    normal, expected state early in a channel's life, not a failure.
    """
    qdrant = get_qdrant()
    query_vector = embed_text(channel_id, query, task_type="RETRIEVAL_QUERY")
    query_tokens = _tokenize(query)

    raw_results = qdrant.search(
        collection,
        vector=query_vector,
        limit=limit * OVER_FETCH_MULTIPLIER,
        query_filter=channel_filter(channel_id, extra_filter),
    )

    scored: list[RetrievedChunk] = []
    for point in raw_results:
        payload = point.get("payload", {}) or {}
        chunk_body = payload.get("text", "")
        vector_score = float(point.get("score", 0.0))
        keyword_score = _keyword_overlap_score(query_tokens, chunk_body)
        combined = VECTOR_WEIGHT * vector_score + KEYWORD_WEIGHT * keyword_score
        scored.append(
            RetrievedChunk(
                text=chunk_body,
                score=combined,
                vector_score=vector_score,
                keyword_score=keyword_score,
                metadata={k: v for k, v in payload.items() if k != "text"},
            )
        )

    scored.sort(key=lambda c: c.score, reverse=True)
    return scored[:limit]


def store_chunks(collection: str, text: str, metadata: dict[str, Any]) -> int:
    """Chunks `text`, embeds each chunk, and upserts them into
    `collection` with `metadata` merged onto every chunk's payload (plus
    the chunk's own text and index). `metadata` must include `channel_id`
    — every collection is filtered on it at query time.

    Returns the number of chunks written.
    """
    if "channel_id" not in metadata:
        raise ValueError("store_chunks: metadata must include channel_id (Ch.12e isolation)")

    qdrant = get_qdrant()
    chunks = chunk_text(text, metadata=metadata)

    points = []
    for chunk in chunks:
        vector = embed_text(metadata["channel_id"], chunk.text, task_type="RETRIEVAL_DOCUMENT")
        payload = dict(chunk.metadata)
        payload["text"] = chunk.text
        payload["chunk_index"] = chunk.index
        points.append({"id": str(uuid.uuid4()), "vector": vector, "payload": payload})

    if points:
        qdrant.upsert(collection, points)
    return len(points)
