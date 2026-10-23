import hashlib
import math
import random

from app.services.embeddings.base import (
    BaseEmbeddingProvider,
    EmbeddingAuthError,
    EmbeddingDimensionMismatchError,
    EmbeddingError,
    EmbeddingRateLimitError,
    EmbeddingTimeoutError,
)


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Deterministic mock embedding provider for tests and local development."""

    def __init__(
        self,
        dimensions: int = 768,
        model_name: str = "mock-embedding-v1",
        simulate_error: str | None = None,
    ):
        self._dimensions = dimensions
        self._model_name = model_name
        self.simulate_error = simulate_error
        self.calls: list[str] = []

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_text(self, text: str) -> list[float]:
        self.calls.append(text)

        if self.simulate_error == "auth":
            raise EmbeddingAuthError("Mock authentication failure")
        elif self.simulate_error == "rate_limit":
            raise EmbeddingRateLimitError("Mock rate limit exceeded")
        elif self.simulate_error == "timeout":
            raise EmbeddingTimeoutError("Mock embedding call timed out")
        elif self.simulate_error == "dimension_mismatch":
            # Intentionally return a vector of different dimension
            return [0.1] * (self._dimensions // 2)
        elif self.simulate_error:
            raise EmbeddingError(f"Mock simulated error: {self.simulate_error}")

        # Deterministic generation from text hash
        # Use sha256 to create a seed
        hash_digest = hashlib.sha256(text.encode("utf-8")).digest()
        seed = int.from_bytes(hash_digest[:8], byteorder="big")
        rng = random.Random(seed)

        # Generate pseudo-random vector
        raw_vec = [rng.gauss(0.0, 1.0) for _ in range(self._dimensions)]

        # L2-normalize vector
        norm = math.sqrt(sum(x * x for x in raw_vec))
        if norm > 0:
            return [round(x / norm, 6) for x in raw_vec]
        return [0.0] * self._dimensions

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]
