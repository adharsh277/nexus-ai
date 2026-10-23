from abc import ABC, abstractmethod


class EmbeddingError(Exception):
    """Base exception for embedding provider errors."""

    def __init__(self, message: str, code: str = "embedding_error"):
        super().__init__(message)
        self.code = code
        self.message = message


class EmbeddingAuthError(EmbeddingError):
    def __init__(self, message: str = "Invalid or missing embedding API credentials"):
        super().__init__(message, code="embedding_auth_error")


class EmbeddingRateLimitError(EmbeddingError):
    def __init__(self, message: str = "Embedding API rate limit or quota exceeded"):
        super().__init__(message, code="embedding_rate_limit_error")


class EmbeddingTimeoutError(EmbeddingError):
    def __init__(self, message: str = "Embedding request timed out"):
        super().__init__(message, code="embedding_timeout_error")


class EmbeddingDimensionMismatchError(EmbeddingError):
    def __init__(self, expected: int, actual: int):
        super().__init__(
            f"Embedding dimension mismatch: expected {expected}, got {actual}",
            code="embedding_dimension_mismatch",
        )
        self.expected = expected
        self.actual = actual


class BaseEmbeddingProvider(ABC):
    """Abstract base class for all embedding providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g., 'gemini', 'ollama', 'mock')."""
        raise NotImplementedError

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model identifier used for embeddings."""
        raise NotImplementedError

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """The dimensionality of vectors produced by this provider."""
        raise NotImplementedError

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Generate a single embedding vector for a piece of text."""
        raise NotImplementedError

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts. Default sequentially calls embed_text."""
        return [self.embed_text(t) for t in texts]
