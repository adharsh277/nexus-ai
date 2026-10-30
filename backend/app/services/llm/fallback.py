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

    if candidate_str:
        try:
            data = json.loads(candidate_str)
            if isinstance(data, dict):
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
        except (json.JSONDecodeError, ValueError):
            pass

    # 3. Check for <tool_code> ... </tool_code> or Python-like call safely via AST (never exec/eval)
    tool_code_match = re.search(r"<tool_code>\s*([\s\S]*?)\s*</tool_code>", trimmed)
    if tool_code_match or "default_api." in trimmed:
        code_to_parse = tool_code_match.group(1).strip() if tool_code_match else trimmed
        import ast
        try:
            tree = ast.parse(code_to_parse)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_name = None
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr
                    # Ignore wrapper calls like print(...)
                    if func_name == "print" and node.args:
                        first_arg = node.args[0]
                        if isinstance(first_arg, ast.Call):
                            node = first_arg
                            if isinstance(node.func, ast.Name):
                                func_name = node.func.id
                            elif isinstance(node.func, ast.Attribute):
                                func_name = node.func.attr

                    if func_name and func_name != "print":
                        kwargs: dict[str, Any] = {}
                        for kw in node.keywords:
                            if kw.arg:
                                try:
                                    kwargs[kw.arg] = ast.literal_eval(kw.value)
                                except Exception:
                                    pass
                        call_id = f"call_{uuid.uuid4().hex[:8]}"
                        return ToolCall(id=call_id, name=func_name, arguments=kwargs)
        except Exception as exc:
            logger.debug("Safe AST parsing of tool_code failed: %s", exc)

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
