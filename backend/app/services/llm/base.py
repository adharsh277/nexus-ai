from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

LLMRole = Literal["user", "assistant", "system", "tool"]


@dataclass
class LLMMessage:
    role: LLMRole
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    raw_response: dict[str, Any] | None = None


class LLMError(Exception):
    """Base exception for LLM provider errors."""

    def __init__(self, message: str, code: str = "llm_error"):
        super().__init__(message)
        self.code = code
        self.message = message


class LLMAuthError(LLMError):
    """Raised when provider authentication fails (e.g., invalid API key)."""

    def __init__(self, message: str = "Invalid or missing LLM API credentials"):
        super().__init__(message, code="llm_auth_error")


class LLMRateLimitError(LLMError):
    """Raised when provider rate limit / quota is exceeded."""

    def __init__(self, message: str = "LLM rate limit or quota exceeded. Please try again shortly."):
        super().__init__(message, code="llm_rate_limit_error")


class LLMTimeoutError(LLMError):
    """Raised when the LLM provider call times out."""

    def __init__(self, message: str = "LLM request timed out."):
        super().__init__(message, code="llm_timeout_error")


class LLMUnavailableError(LLMError):
    """Raised when the LLM service is temporarily down or unreachable."""

    def __init__(self, message: str = "LLM service is currently unavailable."):
        super().__init__(message, code="llm_unavailable_error")


class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    @abstractmethod
    def generate_reply(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Synchronously generate an LLM response given a bounded conversation history."""
        raise NotImplementedError
