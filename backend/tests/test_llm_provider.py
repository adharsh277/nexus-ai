import pytest
from app.services.llm.base import LLMMessage
from app.services.llm.gemini import GeminiProvider
from app.services.llm.mock import MockProvider
from app.services.llm.registry import ToolRegistry
from app.services.llm.factory import create_llm_provider


def test_tool_registry():
    registry = ToolRegistry()
    registry.register(
        name="test_tool",
        description="A test tool",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )

    tool = registry.get("test_tool")
    assert tool is not None
    assert tool.name == "test_tool"
    assert tool.description == "A test tool"

    schema = registry.to_schema()
    assert len(schema) == 1
    assert schema[0]["name"] == "test_tool"


def test_gemini_message_formatting():
    provider = GeminiProvider(api_key="dummy_key_for_unit_tests")
    messages = [
        LLMMessage(role="user", content="Hello"),
        LLMMessage(role="assistant", content="Hi there"),
        LLMMessage(role="user", content="How are you?"),
    ]
    formatted = provider._format_messages(messages)
    assert len(formatted) == 3
    assert formatted[0].role == "user"
    assert formatted[0].parts[0].text == "Hello"
    assert formatted[1].role == "model"
    assert formatted[1].parts[0].text == "Hi there"
    assert formatted[2].role == "user"
    assert formatted[2].parts[0].text == "How are you?"


def test_factory_mock_provider():
    provider = create_llm_provider("mock")
    assert isinstance(provider, MockProvider)
