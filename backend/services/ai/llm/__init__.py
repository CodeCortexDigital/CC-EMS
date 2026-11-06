"""LLM provider selection.

AI_PROVIDER picks the adapter ("openai", "anthropic" or "gemini"); when unset, the first
provider with an API key configured is used. AI_MODEL_FAST / AI_MODEL_SMART
override the provider's default models.
"""
from __future__ import annotations

import logging

from django.conf import settings

from .base import LLMClient, LLMError, LLMTurn, StreamEvent, ToolCall, Usage

logger = logging.getLogger("erp.ai")

DEFAULT_MODELS = {
    "openai": {"fast": "gpt-4o-mini", "smart": "gpt-4o-mini"},
    "anthropic": {"fast": "claude-sonnet-5-5", "smart": "claude-sonnet-5-5"},
    "gemini": {"fast": "gemini-flash-lite-latest", "smart": "gemini-flash-lite-latest"},
}
# Gemini is reached through Google's OpenAI-compatible endpoint, so it uses the OpenAI adapter.
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

__all__ = ["LLMClient", "LLMError", "LLMTurn", "StreamEvent", "ToolCall", "Usage", "get_llm_client"]


def _provider() -> str:
    explicit = (getattr(settings, "AI_PROVIDER", "") or "").lower()
    if explicit:
        return explicit
    if getattr(settings, "OPENAI_API_KEY", ""):
        return "openai"
    if getattr(settings, "ANTHROPIC_API_KEY", ""):
        return "anthropic"
    if getattr(settings, "GEMINI_API_KEY", ""):
        return "gemini"
    return ""


def get_llm_client() -> LLMClient | None:
    """The configured client, or None when no provider is configured/installed."""
    provider = _provider()
    if provider not in DEFAULT_MODELS:
        if provider:
            logger.error("Unknown AI_PROVIDER %r", provider)
        return None
    defaults = dict(DEFAULT_MODELS[provider])
    if provider == "openai" and getattr(settings, "OPENAI_MODEL", ""):
        defaults = {"fast": settings.OPENAI_MODEL, "smart": settings.OPENAI_MODEL}
    if provider == "gemini" and getattr(settings, "GEMINI_MODEL", ""):
        defaults = {"fast": settings.GEMINI_MODEL, "smart": settings.GEMINI_MODEL}
    fast = getattr(settings, "AI_MODEL_FAST", "") or defaults["fast"]
    smart = getattr(settings, "AI_MODEL_SMART", "") or defaults["smart"]
    try:
        if provider == "openai":
            key = getattr(settings, "OPENAI_API_KEY", "")
            if not key:
                return None
            from .openai_client import OpenAIClient
            return OpenAIClient(key, fast_model=fast, smart_model=smart)
        if provider == "gemini":
            key = getattr(settings, "GEMINI_API_KEY", "")
            if not key:
                return None
            from .openai_client import OpenAIClient
            return OpenAIClient(key, fast_model=fast, smart_model=smart, base_url=GEMINI_BASE_URL, provider="gemini")
        key = getattr(settings, "ANTHROPIC_API_KEY", "")
        if not key:
            return None
        from .anthropic_client import AnthropicClient
        return AnthropicClient(key, fast_model=fast, smart_model=smart,
                               effort=getattr(settings, "AI_CLAUDE_EFFORT", "medium"))
    except ImportError:
        logger.error("SDK for AI provider %r is not installed", provider)
        return None
