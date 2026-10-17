"""Minimal custom tool registry interface.

Designed for future Phase capabilities (tasks, reminders, calendar, etc.)
without introducing heavy multi-agent frameworks.
"""
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any] | None = None


class ToolRegistry:
    """Simple in-memory registry of agent tools."""

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable[..., Any] | None = None,
    ) -> ToolDefinition:
        tool = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
        )
        self._tools[name] = tool
        return tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def to_schema(self) -> list[dict[str, Any]]:
        """Return tool definitions formatted for LLM function calling schemas."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            }
            for t in self._tools.values()
        ]


# Global tool registry instance ready for Phase 2 tool bindings
tool_registry = ToolRegistry()
