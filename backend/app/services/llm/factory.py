import logging
from functools import lru_cache

from app.config import settings
from app.services.llm.base import BaseLLMProvider, LLMError
from app.services.llm.gemini import GeminiProvider
from app.services.llm.mock import MockProvider

logger = logging.getLogger("nexus.llm.factory")


def create_llm_provider(provider_name: str | None = None) -> BaseLLMProvider:
    """Factory creating an LLM provider based on configuration or explicit parameter."""
    provider = (provider_name or settings.llm_provider).lower().strip()

    if provider == "gemini":
        return GeminiProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            temperature=settings.llm_temperature,
            max_output_tokens=settings.llm_max_output_tokens,
            timeout_seconds=settings.llm_timeout_seconds,
        )

    if provider == "mock":
        return MockProvider()

    raise LLMError(f"Unsupported LLM provider: '{provider}'. Supported options: 'gemini', 'mock'.")


_cached_provider: BaseLLMProvider | None = None


def get_llm_provider() -> BaseLLMProvider:
    """Return the active singleton LLM provider instance."""
    global _cached_provider
    if _cached_provider is None:
        _cached_provider = create_llm_provider()
    return _cached_provider


def override_llm_provider(provider: BaseLLMProvider | None) -> None:
    """Override the active LLM provider (useful for tests)."""
    global _cached_provider
    _cached_provider = provider
