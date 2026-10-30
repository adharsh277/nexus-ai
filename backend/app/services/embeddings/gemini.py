import logging
from google import genai
from google.genai import errors

from app.services.embeddings.base import (
    BaseEmbeddingProvider,
    EmbeddingAuthError,
    EmbeddingDimensionMismatchError,
    EmbeddingError,
    EmbeddingRateLimitError,
    EmbeddingTimeoutError,
)

logger = logging.getLogger("nexus.embeddings.gemini")


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    """Google Gemini embedding provider using official google-genai SDK."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-embedding-001",
        dimensions: int = 768,
        timeout_seconds: float = 30.0,
    ):
        if not api_key:
            raise EmbeddingAuthError("GEMINI_API_KEY is not configured in backend environment")
        self.api_key = api_key
        self._model_name = model_name
        self._dimensions = dimensions
        self.timeout_seconds = timeout_seconds

        try:
            self.client = genai.Client(api_key=self.api_key)
        except Exception as exc:
            logger.error("Failed to initialize Google GenAI client for embeddings: %s", type(exc).__name__)
            raise EmbeddingAuthError("Failed to initialize Gemini embedding client") from exc

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_text(self, text: str) -> list[float]:
        results = self.embed_batch([text])
        if not results:
            raise EmbeddingError("Gemini returned empty embedding response")
        return results[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        try:
            from google.genai import types
            logger.info("Calling Gemini embed_content model=%s for %d text(s)", self._model_name, len(texts))
            config = types.EmbedContentConfig(output_dimensionality=self._dimensions)
            response = self.client.models.embed_content(
                model=self._model_name,
                contents=texts,
                config=config,
            )

            if not response or not response.embeddings:
                raise EmbeddingError("No embeddings returned by Gemini provider")

            result: list[list[float]] = []
            for emb in response.embeddings:
                values = emb.values or []
                if len(values) != self._dimensions:
                    raise EmbeddingDimensionMismatchError(expected=self._dimensions, actual=len(values))
                result.append(values)

            return result

        except errors.APIError as exc:
            status_code = getattr(exc, "code", None)
            err_msg = str(exc)
            logger.warning("Gemini APIError during embedding: code=%s: %s", status_code, type(exc).__name__)

            if status_code == 429 or "RESOURCE_EXHAUSTED" in err_msg or "rate limit" in err_msg.lower():
                raise EmbeddingRateLimitError(
                    "Gemini API rate limit exceeded during embedding. Please try again shortly."
                ) from exc
            if status_code in (401, 403) or "PERMISSION_DENIED" in err_msg or "UNAUTHENTICATED" in err_msg:
                raise EmbeddingAuthError("Invalid or unauthorized Gemini API key.") from exc
            if status_code in (503, 504) or "UNAVAILABLE" in err_msg:
                raise EmbeddingTimeoutError("Gemini service is temporarily unavailable.") from exc

            raise EmbeddingError("Gemini service encountered an error while generating embeddings.") from exc

        except TimeoutError as exc:
            logger.warning("Gemini embedding request timed out")
            raise EmbeddingTimeoutError("Gemini embedding request timed out.") from exc

        except EmbeddingDimensionMismatchError:
            raise

        except Exception as exc:
            logger.exception("Unexpected error during Gemini embedding: %s", type(exc).__name__)
            raise EmbeddingError(f"Failed to generate embeddings: {exc}") from exc
