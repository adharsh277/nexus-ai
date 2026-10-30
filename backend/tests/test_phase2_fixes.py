import pytest
from app.services.llm.registry import tool_registry, dereference_schema
from app.agent.orchestrator import sanitize_assistant_output, get_agent_system_prompt
from app.services.llm.fallback import parse_fallback_tool_call
from app.services.llm.gemini import GeminiProvider

def test_all_tool_schemas_dereferenced():
    """Verify none of the registered tools have $defs, $ref or illegal fields."""
    for tool in tool_registry.list_tools():
        params = tool.parameters
        assert "$defs" not in params
        assert "$ref" not in str(params)
        assert "anyOf" not in str(params)
        assert params.get("type") == "object"
        assert "properties" in params

def test_sanitize_assistant_output():
    """Verify tool tags and raw code blocks are scrubbed."""
    raw = "Here is your response: <tool_code> print(default_api.list_reminders()) </tool_code> Done!"
    cleaned = sanitize_assistant_output(raw)
    assert "<tool_code>" not in cleaned
    assert "default_api" not in cleaned
    assert "Here is your response:" in cleaned
    assert "Done!" in cleaned

def test_parse_fallback_ast_safe():
    """Verify Python tool syntax is safely parsed without arbitrary execution."""
    code_text = '<tool_code> default_api.create_reminder(title="Doctor", due_at="2026-10-31T09:00:00Z") </tool_code>'
    tc = parse_fallback_tool_call(code_text)
    assert tc is not None
    assert tc.name == "create_reminder"
    assert tc.arguments == {"title": "Doctor", "due_at": "2026-10-31T09:00:00Z"}

def test_system_prompt_temporal_grounding():
    """Verify system prompt contains current 2026 date and context."""
    prompt = get_agent_system_prompt()
    assert "2026" in prompt
    assert "TEMPORAL CONTEXT" in prompt
    assert "list_reminders" in prompt
