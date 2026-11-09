"""Provider selection.

A remote provider is used only when it is configured *and* the operator has
explicitly opted in with ``ALLOW_REMOTE_AI=true``.  Anything else falls back to
the offline provider, and the report says so.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ...config import get_settings
from .base import LLMProvider
from .offline import OfflineProvider

log = logging.getLogger(__name__)
_cached: Optional[LLMProvider] = None
_cached_signature: Optional[tuple] = None


def get_llm(force_reload: bool = False) -> LLMProvider:
    global _cached, _cached_signature
    s = get_settings()
    signature = (s.llm_provider, s.llm_model, bool(s.llm_api_key), s.allow_remote_ai, s.llm_base_url)
    if _cached is not None and signature == _cached_signature and not force_reload:
        return _cached

    provider: LLMProvider
    name = (s.llm_provider or "offline").lower()
    if name in ("offline", "none", ""):
        provider = OfflineProvider()
    elif not s.allow_remote_ai:
        log.warning("LLM provider '%s' configured but ALLOW_REMOTE_AI is false; staying offline.", name)
        provider = OfflineProvider()
        provider.last_error = (
            "Provider '{}' is configured but remote AI processing has not been enabled "
            "(set ALLOW_REMOTE_AI=true to permit document text to leave this machine).".format(name)
        )
    elif not s.llm_api_key:
        provider = OfflineProvider()
        provider.last_error = "Provider '{}' is configured but no API key was supplied.".format(name)
    elif name == "anthropic":
        from .anthropic_provider import AnthropicProvider

        provider = AnthropicProvider(
            api_key=s.llm_api_key, model=s.llm_model, max_tokens=s.llm_max_tokens,
            timeout=s.llm_timeout_seconds, max_retries=s.llm_max_retries,
            max_chars=s.llm_max_chars_per_call, base_url=s.llm_base_url,
        )
    else:
        provider = OfflineProvider()
        provider.last_error = "Unknown LLM provider '{}'.".format(name)

    _cached, _cached_signature = provider, signature
    return provider


def provider_status() -> Dict[str, Any]:
    s = get_settings()
    provider = get_llm()
    info = provider.describe()
    info["configured_provider"] = s.llm_provider
    info["allow_remote_ai"] = s.allow_remote_ai
    info["data_leaving_device"] = (
        "Document text (truncated to {} characters per call) and extracted field values are sent to "
        "the '{}' API.".format(s.llm_max_chars_per_call, provider.name)
        if provider.remote and provider.available
        else "Nothing. All processing is local."
    )
    return info


def reset_llm_cache() -> None:
    global _cached, _cached_signature
    _cached, _cached_signature = None, None
