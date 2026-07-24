"""
Thin wrapper around Qdrant's REST API.

Same design choice as app/core/redis_client.py: a plain HTTPS wrapper
around the subset of commands this project needs, instead of pulling in
the full `qdrant-client` SDK. Two reasons to keep it this thin:

1. Consistency — this codebase already has one pattern for "external
   stateful service, talk to it over REST via httpx" (Redis/Upstash,
   Serper). A second, different pattern (a heavyweight SDK with its own
   connection/retry/serialization conventions) would be one more thing
   to learn for no real benefit at this project's scale.
2. Testability — every other external REST dependency in this codebase
   is faked in tests via `httpx.MockTransport` (see
   tests/phase4_langgraph_test.py's FakeUpstash). The same trick works
   here for free; mocking the official SDK's internals would not be as
   clean.

Env vars required:
    QDRANT_URL       e.g. https://xyz-example.us-east.aws.cloud.qdrant.io:6333
    QDRANT_API_KEY

Usage:
    from app.core.qdrant_client import get_qdrant

    qdrant = get_qdrant()
    qdrant.ensure_collection("research", vector_size=768)
    qdrant.upsert("research", [{"id": "...", "vector": [...], "payload": {...}}])
    qdrant.search("research", vector=[...], limit=5, query_filter=channel_filter("ai_carryon"))
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx


def channel_filter(channel_id: str, extra: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Builds the Qdrant filter clause every query in this project should
    use (Ch.09: "metadata... so retrieval can filter... before it ranks
    by similarity"; Ch.12e: every Qdrant query carries a mandatory
    channel_id filter). `extra`, if given, is merged in as additional
    `must` conditions (each already in Qdrant's `{key, match}` shape).
    """
    must = [{"key": "channel_id", "match": {"value": channel_id}}]
    if extra:
        must.extend(extra.get("must", []))
    return {"must": must}


class QdrantClient:
    """A minimal synchronous client for the subset of the Qdrant REST API
    this project needs: collection create/check, point upsert, vector
    search, and point count.
    """

    def __init__(self, url: Optional[str] = None, api_key: Optional[str] = None):
        base_url = url or os.environ["QDRANT_URL"]
        auth_key = api_key if api_key is not None else os.environ.get("QDRANT_API_KEY", "")

        self._base_url = base_url.rstrip("/")
        headers = {"Content-Type": "application/json"}
        if auth_key:
            headers["api-key"] = auth_key
        self._client = httpx.Client(base_url=self._base_url, headers=headers, timeout=15.0)

    def collection_exists(self, name: str) -> bool:
        response = self._client.get(f"/collections/{name}")
        if response.status_code == 404:
            return False
        response.raise_for_status()
        return True

    def create_payload_index(self, collection: str, field_name: str, field_schema: str = "keyword") -> None:
        """Creates a payload index on `field_name` so it can be used in a
        query filter. Qdrant Cloud rejects any filter on an un-indexed
        field with a 400 ("Index required but not found") — this was
        caught by a real run against a real cluster, not by the faked
        test server, which didn't enforce this. Idempotent: calling this
        again on an already-indexed field is a harmless no-op per
        Qdrant's own API (it returns success either way).
        """
        response = self._client.put(
            f"/collections/{collection}/index",
            json={"field_name": field_name, "field_schema": field_schema},
        )
        response.raise_for_status()

    def ensure_collection(self, name: str, vector_size: int, distance: str = "Cosine") -> None:
        """Creates `name` with the given vector size/distance if it
        doesn't already exist. Safe to call every process start — this is
        what backend/ai/rag/collections.py's `ensure_collections()` calls
        for each of the nine Ch.10 collections.

        Always also ensures a `channel_id` payload index exists (see
        `create_payload_index`), whether the collection is newly created
        or already existed — every collection this project creates is
        queried with a mandatory `channel_id` filter (Ch.12e isolation,
        via `channel_filter()`), so the index isn't optional.
        """
        if not self.collection_exists(name):
            response = self._client.put(
                f"/collections/{name}",
                json={"vectors": {"size": vector_size, "distance": distance}},
            )
            response.raise_for_status()

        self.create_payload_index(name, "channel_id", field_schema="keyword")

    def upsert(self, collection: str, points: list[dict[str, Any]]) -> None:
        """`points`: list of {"id": str|int, "vector": [float,...], "payload": {...}}."""
        response = self._client.put(
            f"/collections/{collection}/points",
            params={"wait": "true"},
            json={"points": points},
        )
        response.raise_for_status()

    def search(
        self,
        collection: str,
        vector: list[float],
        limit: int = 10,
        query_filter: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """Returns Qdrant's raw result list: [{"id", "score", "payload"}, ...],
        ranked by vector similarity only — hybrid re-ranking with keyword
        overlap happens one layer up, in backend/ai/rag/retriever.py.
        """
        body: dict[str, Any] = {"vector": vector, "limit": limit, "with_payload": True}
        if query_filter:
            body["filter"] = query_filter
        response = self._client.post(f"/collections/{collection}/points/search", json=body)
        response.raise_for_status()
        return response.json()["result"]

    def count(self, collection: str, query_filter: Optional[dict[str, Any]] = None) -> int:
        body: dict[str, Any] = {"exact": True}
        if query_filter:
            body["filter"] = query_filter
        response = self._client.post(f"/collections/{collection}/points/count", json=body)
        response.raise_for_status()
        return int(response.json()["result"]["count"])


_client: Optional[QdrantClient] = None


def get_qdrant() -> QdrantClient:
    """Returns a shared, lazily-created QdrantClient — same singleton
    pattern as app.core.redis_client.get_redis().
    """
    global _client
    if _client is None:
        _client = QdrantClient()
    return _client
