import math
from unittest.mock import MagicMock, patch

import pytest

from app.services.embeddings import (
    EmbeddingAuthError,
    EmbeddingDimensionMismatchError,
    EmbeddingError,
    EmbeddingRateLimitError,
    EmbeddingTimeoutError,
    GeminiEmbeddingProvider,
    MockEmbeddingProvider,
    OllamaEmbeddingProvider,
    create_embedding_provider,
    get_embedding_provider,
    override_embedding_provider,
)


def test_mock_embedding_provider_deterministic_and_normalized():
    provider = MockEmbeddingProvider(dimensions=768)
    assert provider.dimensions == 768
    assert provider.provider_name == "mock"

    vec1 = provider.embed_text("Nexus AI local autonomous system")
    vec2 = provider.embed_text("Nexus AI local autonomous system")
    vec3 = provider.embed_text("Completely different topic on biology")

    # Identical text produces identical vectors
    assert vec1 == vec2
    assert len(vec1) == 768

    # Different text produces distinct vectors
    assert vec1 != vec3

    # Vector is normalized (L2 norm is approximately 1.0)
    norm = math.sqrt(sum(x * x for x in vec1))
    assert pytest.approx(norm, rel=1e-3) == 1.0


def test_mock_embedding_provider_custom_dimensions():
    p384 = MockEmbeddingProvider(dimensions=384)
    assert len(p384.embed_text("sample")) == 384

    p1024 = MockEmbeddingProvider(dimensions=1024)
    assert len(p1024.embed_text("sample")) == 1024


def test_mock_embedding_provider_error_simulation():
    p_auth = MockEmbeddingProvider(simulate_error="auth")
    with pytest.raises(EmbeddingAuthError):
        p_auth.embed_text("sample")

    p_rate = MockEmbeddingProvider(simulate_error="rate_limit")
    with pytest.raises(EmbeddingRateLimitError):
        p_rate.embed_text("sample")

    p_timeout = MockEmbeddingProvider(simulate_error="timeout")
    with pytest.raises(EmbeddingTimeoutError):
        p_timeout.embed_text("sample")

    p_mismatch = MockEmbeddingProvider(simulate_error="dimension_mismatch", dimensions=768)
    assert len(p_mismatch.embed_text("sample")) != 768


def test_gemini_embedding_provider_requires_api_key():
    with pytest.raises(EmbeddingAuthError, match="GEMINI_API_KEY is not configured"):
        GeminiEmbeddingProvider(api_key="")


@patch("app.services.embeddings.gemini.genai.Client")
def test_gemini_embedding_provider_embed_batch(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    # Mock embed_content response with 768-dim vectors
    fake_item1 = MagicMock()
    fake_item1.values = [0.1] * 768
    fake_item2 = MagicMock()
    fake_item2.values = [0.2] * 768

    mock_resp = MagicMock()
    mock_resp.embeddings = [fake_item1, fake_item2]
    mock_client.models.embed_content.return_value = mock_resp

    provider = GeminiEmbeddingProvider(api_key="test-key", dimensions=768)
    vectors = provider.embed_batch(["text1", "text2"])

    assert len(vectors) == 2
    assert len(vectors[0]) == 768
    assert vectors[0][0] == 0.1
    assert vectors[1][0] == 0.2


@patch("app.services.embeddings.gemini.genai.Client")
def test_gemini_embedding_provider_detects_dimension_mismatch(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    fake_item = MagicMock()
    fake_item.values = [0.1] * 384  # Mismatched dimension (expected 768)

    mock_resp = MagicMock()
    mock_resp.embeddings = [fake_item]
    mock_client.models.embed_content.return_value = mock_resp

    provider = GeminiEmbeddingProvider(api_key="test-key", dimensions=768)
    with pytest.raises(EmbeddingDimensionMismatchError) as exc_info:
        provider.embed_text("test")

    assert exc_info.value.expected == 768
    assert exc_info.value.actual == 384


@patch("httpx.Client.post")
def test_ollama_embedding_provider_success(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"embedding": [0.05] * 768}
    mock_post.return_value = mock_resp

    provider = OllamaEmbeddingProvider(
        base_url="http://localhost:11434",
        model_name="nomic-embed-text",
        dimensions=768,
    )
    vec = provider.embed_text("test query")
    assert len(vec) == 768
    assert vec[0] == 0.05


@patch("httpx.Client.post")
def test_ollama_embedding_provider_dimension_mismatch(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"embedding": [0.05] * 512}  # expected 768
    mock_post.return_value = mock_resp

    provider = OllamaEmbeddingProvider(dimensions=768)
    with pytest.raises(EmbeddingDimensionMismatchError):
        provider.embed_text("test query")


def test_factory_and_override():
    mock_p = MockEmbeddingProvider()
    override_embedding_provider(mock_p)
    assert get_embedding_provider() is mock_p

    override_embedding_provider(None)
    created = create_embedding_provider("mock")
    assert isinstance(created, MockEmbeddingProvider)

    with pytest.raises(EmbeddingError, match="Unsupported embedding provider"):
        create_embedding_provider("nonexistent_provider")
