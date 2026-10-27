from typing import Any

from app.services.llm.base import (
    BaseLLMProvider,
    LLMAuthError,
    LLMError,
    LLMMessage,
    LLMRateLimitError,
    LLMResponse,
    LLMTimeoutError,
    LLMUnavailableError,
    ToolCall,
)


class MockProvider(BaseLLMProvider):
    """Mock LLM provider for deterministic unit testing and offline development."""

    def __init__(
        self,
        default_reply: str = "This is a mock assistant response.",
        simulate_error: str | None = None,
        responses: list[LLMResponse] | None = None,
        tool_calls: list[ToolCall] | None = None,
        supports_native_tools: bool = True,
    ):
        self.default_reply = default_reply
        self.simulate_error = simulate_error
        self.responses: list[LLMResponse] = list(responses) if responses else []
        self.tool_calls: list[ToolCall] = list(tool_calls) if tool_calls else []
        self.supports_native_tools = supports_native_tools
        self.calls: list[dict[str, Any]] = []

    def generate_reply(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        self.calls.append({
            "messages": messages,
            "system_prompt": system_prompt,
            "tools": tools,
        })

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

        # 1. If sequential canned responses are configured, pop the next one
        if self.responses:
            return self.responses.pop(0)

        # 2. If configured with tool_calls, return them on the first call then clear
        if self.tool_calls:
            calls = self.tool_calls
            self.tool_calls = []
            return LLMResponse(
                content="",
                model="mock-llm-v1",
                tool_calls=calls,
                raw_response={"status": "mock_tool_call"},
            )

        # 3. Default mock echo behavior
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        content = f"Mock AI Echo: {last_user}" if last_user else self.default_reply

        return LLMResponse(
            content=content,
            model="mock-llm-v1",
            raw_response={"status": "mock_success"},
        )
