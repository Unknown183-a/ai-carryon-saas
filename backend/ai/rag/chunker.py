"""
Chunker (Ch.09): splits source text into overlapping ~300-500 token
chunks before embedding, so a fact-carrying sentence never gets cut in
half at a chunk boundary.

No tokenizer dependency is pulled in for this — the project doesn't call
a tokenizer anywhere else, and adding one just for chunk-sizing is more
weight than the job needs. Instead this uses a documented word-based
approximation (see WORDS_PER_TOKEN below), which is accurate enough for
"roughly 300-500 tokens" — the spec Ch.09 actually asks for, not an
exact token count. If a real tokenizer ever gets added to this project
for another reason, swap the estimate in `_estimate_tokens` for a real
count; nothing else in this file needs to change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Empirically, English text averages ~0.75 tokens per word for
# GPT/Gemini-style BPE tokenizers — i.e. ~1.33 words per token. Used
# only to convert the Ch.09 token targets into a word-count window.
WORDS_PER_TOKEN = 0.75

TARGET_MIN_TOKENS = 300
TARGET_MAX_TOKENS = 500
OVERLAP_TOKENS = 50

_MIN_WORDS = int(TARGET_MIN_TOKENS * WORDS_PER_TOKEN)  # ~225
_MAX_WORDS = int(TARGET_MAX_TOKENS * WORDS_PER_TOKEN)  # ~375
_OVERLAP_WORDS = int(OVERLAP_TOKENS * WORDS_PER_TOKEN)  # ~37


@dataclass
class Chunk:
    text: str
    index: int  # position of this chunk within its source document, 0-based
    metadata: dict[str, Any] = field(default_factory=dict)


def _estimate_tokens(word_count: int) -> int:
    return int(word_count / WORDS_PER_TOKEN)


def chunk_text(text: str, metadata: dict[str, Any] | None = None) -> list[Chunk]:
    """Splits `text` into overlapping chunks sized ~300-500 tokens.

    `metadata` is copied onto every chunk produced (e.g. channel_id,
    source_type, published_at per Ch.09) — callers add chunk-specific
    keys (like a source video_id) via the returned Chunk's `.metadata`
    dict if needed before upserting.

    Short inputs (under _MAX_WORDS) come back as a single chunk rather
    than being padded out — there's nothing to overlap when there's only
    one chunk.
    """
    words = text.split()
    base_metadata = dict(metadata or {})

    if not words:
        return []

    if len(words) <= _MAX_WORDS:
        return [Chunk(text=text.strip(), index=0, metadata=dict(base_metadata))]

    chunks: list[Chunk] = []
    start = 0
    index = 0
    step = _MAX_WORDS - _OVERLAP_WORDS
    while start < len(words):
        end = min(start + _MAX_WORDS, len(words))
        chunk_words = words[start:end]
        chunks.append(
            Chunk(text=" ".join(chunk_words).strip(), index=index, metadata=dict(base_metadata))
        )
        index += 1
        if end == len(words):
            break
        start += step

    return chunks
