from app.services.llm.base import (
    BaseLLMProvider,
    LLMAuthError,
    LLMError,
    LLMMessage,
    LLMRateLimitError,
    LLMResponse,
    LLMTimeoutError,
    LLMUnavailableError,
)


class MockProvider(BaseLLMProvider):
    """Mock LLM provider for deterministic unit testing and offline development."""

    def __init__(
        self,
        default_reply: str = "This is a mock assistant response.",
        simulate_error: str | None = None,
    ):
        self.default_reply = default_reply
        self.simulate_error = simulate_error
        self.calls: list[dict] = []

    def generate_reply(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
    ) -> LLMResponse:
        self.calls.append({"messages": messages, "system_prompt": system_prompt})

        if self.simulate_error == "rate_limit":
            raise LLMRateLimitError("Simulated rate limit exceeded")
        if self.simulate_error == "auth":
            raise LLMAuthError("Simulated invalid credentials")
        if self.simulate_error == "timeout":
            raise LLMTimeoutError("Simulated timeout error")
        if self.simulate_error == "unavailable":
            raise LLMUnavailableError("Simulated service unavailable")
        if self.simulate_error:
            raise LLMError("Simulated generic LLM failure")

        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        content = f"Mock AI Echo: {last_user}" if last_user else self.default_reply

        return LLMResponse(
            content=content,
            model="mock-llm-v1",
            raw_response={"status": "mock_success"},
        )
