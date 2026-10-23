import logging
import httpx

from app.services.embeddings.base import (
    BaseEmbeddingProvider,
    EmbeddingDimensionMismatchError,
    EmbeddingError,
    EmbeddingTimeoutError,
)

logger = logging.getLogger("nexus.embeddings.ollama")


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    """Local Ollama embedding provider using HTTP REST API."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model_name: str = "nomic-embed-text",
        dimensions: int = 768,
        timeout_seconds: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._dimensions = dimensions
        self.timeout_seconds = timeout_seconds

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_text(self, text: str) -> list[float]:
        results = self.embed_batch([text])
        if not results:
            raise EmbeddingError("Ollama returned empty embedding response")
        return results[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        embeddings: list[list[float]] = []

        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout_seconds) as client:
                for text in texts:
                    # Ollama POST /api/embeddings: {"model": model, "prompt": prompt}
                    response = client.post(
                        "/api/embeddings",
                        json={"model": self._model_name, "prompt": text},
                    )

                    if response.status_code != 200:
                        raise EmbeddingError(
                            f"Ollama embedding request failed with HTTP {response.status_code}: {response.text}"
                        )

                    data = response.json()
                    vec = data.get("embedding")
                    if not vec or not isinstance(vec, list):
                        raise EmbeddingError(f"Malformed response from Ollama: {data}")

                    if len(vec) != self._dimensions:
                        raise EmbeddingDimensionMismatchError(expected=self._dimensions, actual=len(vec))

                    embeddings.append(vec)

            return embeddings

        except httpx.TimeoutException as exc:
            logger.warning("Ollama embedding request timed out")
            raise EmbeddingTimeoutError("Ollama embedding request timed out") from exc

        except httpx.ConnectError as exc:
            logger.error("Could not connect to Ollama at %s", self.base_url)
            raise EmbeddingError(f"Cannot reach Ollama at {self.base_url}. Is Ollama running?") from exc

        except EmbeddingDimensionMismatchError:
            raise

        except Exception as exc:
            logger.exception("Error calling Ollama embeddings: %s", type(exc).__name__)
            raise EmbeddingError(f"Ollama embedding error: {exc}") from exc
