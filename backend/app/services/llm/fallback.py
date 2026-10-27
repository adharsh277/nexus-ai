import json
import logging
import re
import uuid
from typing import Any

from app.services.llm.base import BaseLLMProvider, LLMMessage, LLMResponse, ToolCall

logger = logging.getLogger("nexus.llm.fallback")


def format_tools_for_prompt(tools: list[dict[str, Any]]) -> str:
    """Format tool definitions into an explicit prompt section for providers without native tool calling."""
    if not tools:
        return ""

    formatted_tools: list[str] = []
    for tool in tools:
        name = tool.get("name", "unknown")
        desc = tool.get("description", "")
        params = tool.get("parameters", {})
        properties = params.get("properties", {})
        required = params.get("required", [])

        param_lines = []
        for p_name, p_info in properties.items():
            req_str = " (REQUIRED)" if p_name in required else " (optional)"
            p_desc = p_info.get("description", p_info.get("type", "any"))
            param_lines.append(f"    - `{p_name}`{req_str}: {p_desc}")

        param_str = "\n".join(param_lines) if param_lines else "    (no parameters)"
        formatted_tools.append(f"### Tool: `{name}`\n{desc}\nParameters:\n{param_str}")

    tools_text = "\n\n".join(formatted_tools)

    return (
        "\n\n--- AVAILABLE TOOLS ---\n"
        "You have access to the following server tools to assist the user:\n\n"
        f"{tools_text}\n\n"
        "--- TOOL CALLING INSTRUCTIONS ---\n"
        "1. If you need to invoke a tool, you MUST output ONLY a valid JSON object formatted as follows:\n"
        "```json\n"
        "{\n"
        '  "tool": "<tool_name>",\n'
        '  "arguments": {\n'
        '    "<parameter_name>": "<parameter_value>"\n'
        "  }\n"
        "}\n"
        "```\n"
        "2. Do NOT add conversational text before or after the JSON block when invoking a tool.\n"
        "3. If no tool is needed, respond normally with natural conversational text.\n"
        "--- END TOOLS ---"
    )


def parse_fallback_tool_call(content: str) -> ToolCall | None:
    """Safely extract a structured ToolCall from LLM text response, handling JSON blocks or raw JSON."""
    if not content or not content.strip():
        return None

    trimmed = content.strip()

    # 1. Check for markdown json block: ```json ... ```
    json_block = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", trimmed, re.DOTALL)
    candidate_str = json_block.group(1).strip() if json_block else None

    # 2. Check for raw JSON object if no code block found
    if not candidate_str:
        start = trimmed.find("{")
        end = trimmed.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate_str = trimmed[start : end + 1]

    if not candidate_str:
        return None

    try:
        data = json.loads(candidate_str)
        if not isinstance(data, dict):
            return None

        # Support {"tool": "name", "arguments": {...}}
        # Support {"tool_call": {"name": "name", "arguments": {...}}}
        # Support {"name": "name", "arguments": {...}}
        tool_name = None
        tool_args: dict[str, Any] = {}

        if "tool_call" in data and isinstance(data["tool_call"], dict):
            tool_name = data["tool_call"].get("name")
            tool_args = data["tool_call"].get("arguments", {})
        elif "tool" in data:
            tool_name = data.get("tool")
            tool_args = data.get("arguments", {})
        elif "name" in data and "arguments" in data:
            tool_name = data.get("name")
            tool_args = data.get("arguments", {})

        if tool_name and isinstance(tool_name, str):
            if not isinstance(tool_args, dict):
                tool_args = {}
            call_id = f"call_{uuid.uuid4().hex[:8]}"
            return ToolCall(id=call_id, name=tool_name, arguments=tool_args)

    except (json.JSONDecodeError, ValueError) as exc:
        logger.debug("Content appeared to contain JSON but parsing failed: %s", exc)

    return None


def execute_with_fallback(
    provider: BaseLLMProvider,
    messages: list[LLMMessage],
    system_prompt: str | None = None,
    tools: list[dict[str, Any]] | None = None,
) -> LLMResponse:
    """Execute tool-augmented chat with an LLM provider that lacks native function calling."""
    augmented_system = system_prompt or ""
    if tools:
        augmented_system = augmented_system + format_tools_for_prompt(tools)

    # Call provider with standard text turns and augmented prompt
    response = provider.generate_reply(messages=messages, system_prompt=augmented_system, tools=None)

    # Check if the output is a tool call
    tool_call = parse_fallback_tool_call(response.content)
    if tool_call:
        return LLMResponse(
            content="",
            model=response.model,
            raw_response=response.raw_response,
            tool_calls=[tool_call],
        )

    return response
