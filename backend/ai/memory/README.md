Owned by: **Phase 5 — qdrant-rag / Phase 12 — learning-agent. Long-term context: lessons_learned retrieval, prior-run memory.**

`channel_memory.py` (Phase 5): `get_lessons_learned()`, a thin facade over `ai/rag/retriever.py`'s hybrid search scoped to the `lessons_learned` collection. Returns an empty list on every real call until Phase 12's Learning Agent exists and has written at least one pattern — that's expected, not a bug.

See `../../../phases/` for that phase's full brief.
