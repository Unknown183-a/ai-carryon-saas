"""
Provider-agnostic LLM interface.

This is where an agent asks for "run this prompt on this model" and gets
back a normalized string — it does NOT know or care whether that model
lives on Gemini, Groq, or (later) OpenAI. The raw provider calls live in
backend/integrations/{gemini,groq}/client.py; this file decides *which*
one to call and normalizes the interface, per this folder's README.

How a model name resolves to a provider
----------------------------------------
Callers can be explicit — "gemini/gemini-1.5-flash", "groq/llama-3.3-70b-versatile"
— or just name the bare model ("gemini-1.5-flash", "llama-3.3-70b-versatile")
and this module figures out the provider from well-known name patterns.
That's the "name the model, we auto-detect the provider" behavior this
phase asked for. Add a new provider by (1) dropping a thin client in
backend/integrations/<provider>/client.py and (2) adding one line each to
_PROVIDER_CLIENTS and _KNOWN_MODEL_PREFIXES below — agents never change.

Fallback chain
---------------
If the resolved provider's call raises (missing key, rate limit, outage),
call_llm() retries once against the next model in `fallback_models`
before giving up. Default fallback order is defined in DEFAULT_FALLBACK_CHAIN.

# TODO (Phase 6): per-channel model preference resolution — a channel
# picks its own model in the Create-Channel form (Ch.12d) and this layer
# should honor it instead of every agent hardcoding DEFAULT_MODELS below.
# Not built now on purpose; Phase 4 has exactly one hardcoded channel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from integrations.gemini import client as gemini_client
from integrations.groq import client as groq_client

_PROVIDER_CLIENTS: dict[str, Callable] = {
    "gemini": gemini_client.generate,
    "groq": groq_client.generate,
}

# Bare model name -> provider, for callers who don't prefix with "provider/".
# Matched by prefix, longest/most-specific match wins.
_KNOWN_MODEL_PREFIXES: dict[str, str] = {
    "gemini-": "gemini",
    "llama-": "groq",
    "llama3": "groq",
    "mixtral-": "groq",
    "gemma-": "groq",
    "gemma2-": "groq",
    "qwen-": "groq",
    "deepseek-": "groq",
    "whisper-": "groq",
}

# Used by agents that don't get an explicit model override (e.g. from a
# future per-channel config). Ordered cheapest/fastest-first for the tasks
# that don't need the strongest reasoning; the LLM Judge gets the stronger
# model since Ch.08 treats it as the holistic quality gate.
DEFAULT_MODELS = {
    "trend": "gemini/gemini-1.5-flash",
    "research": "gemini/gemini-1.5-flash",
    "planner": "gemini/gemini-1.5-flash",
    "script": "gemini/gemini-1.5-flash",
    "seo": "gemini/gemini-1.5-flash",
    "thumbnail": "gemini/gemini-1.5-flash",
    "hook": "gemini/gemini-1.5-flash",
    "tags": "gemini/gemini-1.5-flash",
    "description": "gemini/gemini-1.5-flash",
    "grammar_check": "gemini/gemini-1.5-flash",
    "fact_check": "gemini/gemini-1.5-flash",
    "copyright_check": "gemini/gemini-1.5-flash",
    "llm_judge": "gemini/gemini-1.5-pro",
}

DEFAULT_FALLBACK_CHAIN = [
    "gemini/gemini-1.5-flash",
    "groq/llama-3.3-70b-versatile",
]


@dataclass
class ResolvedModel:
    provider: str
    model: str


def resolve_model(model_ref: str) -> ResolvedModel:
    """Splits "provider/model" or infers the provider from a bare model name."""
    if "/" in model_ref:
        provider, model = model_ref.split("/", 1)
        provider = provider.lower()
        if provider not in _PROVIDER_CLIENTS:
            raise ValueError(
                f"Unknown provider '{provider}' in model ref '{model_ref}'. "
                f"Known providers: {sorted(_PROVIDER_CLIENTS)}"
            )
        return ResolvedModel(provider=provider, model=model)

    lowered = model_ref.lower()
    for prefix, provider in _KNOWN_MODEL_PREFIXES.items():
        if lowered.startswith(prefix):
            return ResolvedModel(provider=provider, model=model_ref)

    raise ValueError(
        f"Can't auto-detect a provider for model '{model_ref}'. "
        f"Either prefix it explicitly (e.g. 'gemini/{model_ref}') or add its "
        f"prefix to _KNOWN_MODEL_PREFIXES in backend/ai/models/llm_client.py."
    )


def call_llm(
    model: str,
    system_prompt: str,
    user_prompt: str,
    json_mode: bool = False,
    temperature: float = 0.7,
    fallback_models: Optional[list[str]] = None,
) -> str:
    """Runs a prompt against `model`, auto-detecting its provider.

    On failure, tries each entry in `fallback_models` in order (defaults
    to DEFAULT_FALLBACK_CHAIN) before raising the original exception.
    """
    candidates = [model] + [m for m in (fallback_models or DEFAULT_FALLBACK_CHAIN) if m != model]

    last_error: Optional[Exception] = None
    for candidate in candidates:
        try:
            resolved = resolve_model(candidate)
            generate_fn = _PROVIDER_CLIENTS[resolved.provider]
            return generate_fn(
                model=resolved.model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                json_mode=json_mode,
                temperature=temperature,
            )
        except Exception as exc:  # noqa: BLE001 — deliberately broad: any
            # provider failure (bad key, rate limit, outage, bad model name)
            # should fall through to the next candidate, not crash the run.
            last_error = exc
            continue

    raise RuntimeError(
        f"All LLM candidates failed for original model '{model}': {candidates}"
    ) from last_error
