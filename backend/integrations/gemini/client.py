"""
Thin Gemini API client — auth, request formatting, the actual HTTP call.

No "which model for which task" logic here (that's backend/ai/models/ —
the registry that decides *which* client to call). This file only knows
how to talk to Gemini once someone's already decided to.

Uses the current `google-genai` SDK. The older `google.generativeai`
package is fully deprecated (no updates or bug fixes) as of when this was
written — worth remembering if you ever see example code using
`genai.configure()` / `genai.GenerativeModel()`, that's the old package.

Env var required: GEMINI_API_KEY
"""

from __future__ import annotations

import os
from typing import Optional

from google import genai
from google.genai import types

_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add it to .env to use Gemini models."
            )
        _client = genai.Client(api_key=api_key)
    return _client


def generate(
    model: str,
    system_prompt: str,
    user_prompt: str,
    json_mode: bool = False,
    temperature: float = 0.7,
) -> str:
    """Calls a Gemini model and returns the raw text response.

    `model` is the bare Gemini model name (e.g. "gemini-1.5-flash",
    "gemini-1.5-pro") — the "gemini/" provider prefix used elsewhere in
    this codebase is stripped before it gets here.
    """
    client = _get_client()

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=temperature,
        response_mime_type="application/json" if json_mode else "text/plain",
    )

    response = client.models.generate_content(
        model=model,
        contents=user_prompt,
        config=config,
    )
    return response.text


def embed(
    text: str,
    model: str = "gemini-embedding-001",
    task_type: str = "RETRIEVAL_DOCUMENT",
    output_dimensionality: int = 768,
) -> list[float]:
    """Returns a single embedding vector for `text` via Gemini's
    `embed_content` endpoint (Ch.09/Ch.10 — RAG/Qdrant, added Phase 5).

    `output_dimensionality=768` is a deliberate choice, not the model's
    default (3072): it keeps Qdrant collection storage/search cost down,
    and 768 is one of the officially supported Matryoshka truncation
    sizes for gemini-embedding-001, so quality loss is minimal. If this
    ever changes, every existing Qdrant collection needs re-embedding —
    the vector size is fixed per-collection at creation time (see
    backend/ai/rag/collections.py's EMBEDDING_DIM).

    `task_type="RETRIEVAL_DOCUMENT"` is right for text being stored for
    later retrieval (chunks going into Qdrant). Query-time embedding
    (backend/ai/rag/retriever.py) passes "RETRIEVAL_QUERY" instead —
    Gemini's embedding space is asymmetric between the two, and using
    the wrong one measurably hurts retrieval quality.

    Only ever embeds one string per call (matches how this codebase's
    other clients work — one thing in, one thing out); callers needing
    to embed many chunks call this once per chunk. Retries and Redis
    caching live one layer up, in backend/ai/rag/embed.py.
    """
    client = _get_client()

    response = client.models.embed_content(
        model=model,
        contents=text,
        config=types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=output_dimensionality,
        ),
    )
    return list(response.embeddings[0].values)
