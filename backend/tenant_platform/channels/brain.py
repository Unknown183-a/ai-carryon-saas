"""
Channel Brain (Ch.12b): the scoped slice of identity, prompt overrides,
and settings that makes one channel's pipeline runs distinct from every
other channel's, even though all of them run through the identical
LangGraph engine.

Ch.12b lists eight components a Channel Brain "holds": Channel DNA,
Prompt Library (overrides), Analytics, Learning, Viewer Feedback,
Competitor Memory, Redis Namespace, Qdrant Namespace. The last two
aren't fields on this object — they're conventions enforced elsewhere
(`app/core/redis_client.py`'s `channel_key()`, `app/core/qdrant_client.py`'s
`channel_filter()`) precisely because a namespace isn't a piece of data
to carry around, it's a rule every read/write already follows. Analytics,
Learning, Viewer Feedback, and Competitor Memory are Qdrant collections
(Ch.10) with nothing written to them yet — they're per-channel by
construction (every point already carries channel_id) the moment later
phases start writing to them, with no change needed here. What this
class actually holds is the two components that ARE data living on the
Firestore channel document: Channel DNA and Prompt Library overrides.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Fields that describe *this project's* bookkeeping on the Firestore
# document, not the channel's own identity/DNA — excluded from
# `to_pipeline_config()`'s output so the LangGraph state's channel_config
# stays exactly the same shape Phase 4's HARDCODED_CHANNEL already was.
_NON_DNA_FIELDS = {"workspace_id", "status", "created_at", "owner_uid"}


@dataclass
class ChannelBrain:
    channel_id: str
    workspace_id: str
    dna: dict[str, Any]  # niche/region/language/tone/brand voice — same shape as Phase 4's HARDCODED_CHANNEL
    prompt_overrides: dict[str, str] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)

    def to_pipeline_config(self) -> dict[str, Any]:
        """Returns the dict LangGraph's `channel_config` state field
        expects — shape-compatible with Phase 4's `HARDCODED_CHANNEL`,
        so `research_agent.py`, `trend_agent.py`, and every prompt in
        `prompt_library.py` keep working unchanged against a
        database-driven channel instead of the hardcoded one.

        `prompt_overrides` used to be loaded from Firestore onto this
        object and then silently dropped here — every agent's prompt was
        100% fixed regardless of what a channel's own document said.
        That's why a channel whose content doesn't fit the pipeline's
        built-in assumptions (see `content_type` below) had no way to
        steer any agent short of editing prompt_library.py itself, which
        is exactly the "generalized, not hardcoded per-channel" gap this
        fixes: `prompt_overrides` now rides along in `channel_config` so
        every prompt builder in prompt_library.py can layer a channel's
        own per-agent instructions on top of its base prompt, driven
        entirely by Firestore data, no code change needed per channel.

        `content_type` (also just a plain DNA field, defaulted here only
        so every agent can rely on the key existing) is the other half:
        it lets trend_agent/research_agent/script_agent/fact_check branch
        between "factual" behavior (trend-chasing, web-search-grounded,
        claim-traceable — the only mode this pipeline supported before)
        and "narrative" behavior (genre/angle rotation instead of Google
        Trends, RAG-continuity instead of web search, invented plot
        explicitly allowed, consistency-with-premise instead of
        fact-tracing). Any channel picks its mode via this one Firestore
        field; no agent needs a channel-specific branch to add a new one.
        """
        config = dict(self.dna)
        config.setdefault("content_type", "factual")
        config["prompt_overrides"] = dict(self.prompt_overrides)
        return config


def load_channel_brain(channel_doc: dict[str, Any]) -> ChannelBrain:
    """Builds a ChannelBrain from a Firestore `channels/{id}` document,
    as returned by `app.database.firestore_collections.get_channel()`.
    """
    dna = {k: v for k, v in channel_doc.items() if k not in _NON_DNA_FIELDS}
    return ChannelBrain(
        channel_id=channel_doc["channel_id"],
        workspace_id=channel_doc["workspace_id"],
        dna=dna,
        prompt_overrides=channel_doc.get("prompt_overrides", {}),
        settings=channel_doc.get("settings", {}),
    )
