import logging

from app.config import settings
from app.services.embeddings.base import BaseEmbeddingProvider, EmbeddingError
from app.services.embeddings.gemini import GeminiEmbeddingProvider
from app.services.embeddings.mock import MockEmbeddingProvider
from app.services.embeddings.ollama import OllamaEmbeddingProvider

logger = logging.getLogger("nexus.embeddings.factory")


def create_embedding_provider(provider_name: str | None = None) -> BaseEmbeddingProvider:
    """Factory creating an embedding provider based on configuration or explicit parameter."""
    provider = (provider_name or settings.embedding_provider).lower().strip()

    if provider == "gemini":
        return GeminiEmbeddingProvider(
            api_key=settings.gemini_api_key,
            model_name=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
            timeout_seconds=settings.llm_timeout_seconds,
        )

    if provider == "ollama":
        return OllamaEmbeddingProvider(
            base_url=settings.ollama_base_url,
            model_name=settings.ollama_embedding_model,
            dimensions=settings.embedding_dimensions,
            timeout_seconds=settings.llm_timeout_seconds,
        )

    if provider == "mock":
        return MockEmbeddingProvider(
            dimensions=settings.embedding_dimensions,
            model_name="mock-embedding-v1",
        )

    raise EmbeddingError(f"Unsupported embedding provider: '{provider}'. Supported options: 'gemini', 'ollama', 'mock'.")


_cached_provider: BaseEmbeddingProvider | None = None


def get_embedding_provider() -> BaseEmbeddingProvider:
    """Return the active singleton embedding provider instance."""
    global _cached_provider
    if _cached_provider is None:
        _cached_provider = create_embedding_provider()
    return _cached_provider


def override_embedding_provider(provider: BaseEmbeddingProvider | None) -> None:
    """Override the active embedding provider (useful for tests)."""
    global _cached_provider
    _cached_provider = provider
