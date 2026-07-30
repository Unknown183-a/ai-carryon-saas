"""
The nine Qdrant collections from Ch.10 of the SAD, plus `clip_history`
(added for the Clip Agent, not in the original Ch.10 table — same shape
and isolation rules as the other nine, so it didn't need a bespoke
setup path), all in one place.

Every collection shares the same vector size (EMBEDDING_DIM, matching
`output_dimensionality` in integrations/gemini/client.py's `embed()`) and
distance metric — Qdrant collections are cheap, and having every one of
them shaped the same way means one `ensure_collections()` call handles
all nine instead of nine bespoke creation calls.

The `example_metadata` values here are documentation, not schema
enforcement — Qdrant doesn't require a fixed payload shape per
collection. They're taken verbatim from Ch.10's table so anyone reading
this file doesn't have to cross-reference the SAD to know what belongs
in a given collection's payload.
"""

from __future__ import annotations

from app.core.qdrant_client import QdrantClient, get_qdrant

EMBEDDING_DIM = 768  # must match integrations/gemini/client.py's embed() output_dimensionality
DISTANCE_METRIC = "Cosine"

# name -> (what it stores, example metadata keys) — straight from Ch.10's table.
COLLECTIONS: dict[str, dict[str, str]] = {
    "scripts": {
        "stores": "Past video scripts, embedded in full",
        "example_metadata": "channel_id, video_id, views",
    },
    "research": {
        "stores": "Research summaries per topic",
        "example_metadata": "channel_id, topic, source_urls, date",
    },
    "comments": {
        "stores": "Aggregated viewer comment themes",
        "example_metadata": "channel_id, video_id, sentiment",
    },
    "viewer_feedback": {
        "stores": "Structured feedback signals",
        "example_metadata": "channel_id, video_id, retention_drop_ts",
    },
    "competitors": {
        "stores": "Rival channels' titles & hooks",
        "example_metadata": "channel_id, competitor_channel, niche",
    },
    "analytics": {
        "stores": "Per-video performance embeddings",
        "example_metadata": "channel_id, ctr, avg_view_duration",
    },
    "knowledge": {
        "stores": "General domain knowledge base",
        "example_metadata": "channel_id, domain, confidence",
    },
    "prompt_history": {
        "stores": "Prior prompts and their outcomes",
        "example_metadata": "channel_id, agent_name, success",
    },
    "lessons_learned": {
        "stores": "Learning Agent's distilled patterns",
        "example_metadata": "channel_id, pattern, confidence",
    },
    "clip_history": {
        "stores": "Pexels background clips already used, keyed by the script segment/topic that picked them",
        "example_metadata": "channel_id, video_id, clip_url, topic",
    },
}


def ensure_collections(client: QdrantClient | None = None) -> list[str]:
    """Ensures every collection in COLLECTIONS exists AND has its
    channel_id payload index — for every collection, every call, not
    just newly-created ones. Idempotent — safe to call on every process
    start (this is wired into FastAPI's startup in app/api/main.py).
    Returns the list of collection names actually created this call
    (empty on a warm/already-provisioned Qdrant instance).

    Deliberately does NOT pre-check collection_exists() itself before
    calling client.ensure_collection() — that was the original bug here.
    ensure_collection() does its own existence check internally and
    ALSO ensures the payload index every time regardless of whether the
    collection was pre-existing; a pre-check in this loop meant
    ensure_collection() (and therefore the payload index) never even ran
    for any collection that already existed, which was every collection
    on a real Qdrant Cloud cluster the second time this ran. Caught by a
    real run, not the faked test — the fake didn't enforce the payload
    index requirement in the first place, so this double-guard bug had
    no way to surface there.
    """
    client = client or get_qdrant()
    created = []
    for name in COLLECTIONS:
        was_created = client.ensure_collection(name, vector_size=EMBEDDING_DIM, distance=DISTANCE_METRIC)
        if was_created:
            created.append(name)
    return created
