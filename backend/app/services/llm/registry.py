"""Custom tool registry interface for Nexus AI agent capabilities."""
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.services import NotFoundError

logger = logging.getLogger("nexus.llm.registry")


@dataclass
class ToolContext:
    """Trusted server-side execution context for agent tools.
    
    The user_id and db session are injected by the server orchestrator
    and NEVER accepted from LLM-generated arguments.
    """
    user_id: uuid.UUID
    db: Session


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    input_model: type[BaseModel] | None = None
    handler: Callable[[ToolContext, Any], Any] | None = None
    is_read_only: bool = True
    requires_confirmation: bool = False


def dereference_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Resolve all $ref and anyOf constructs into flat OpenAPI-compliant schemas for LLM tools."""
    defs = schema.get("$defs", {})

    def _resolve(node: Any) -> Any:
        if not isinstance(node, dict):
            return node
        res: dict[str, Any] = {}
        for k, v in node.items():
            if k == "$ref":
                ref_key = v.split("/")[-1]
                if ref_key in defs:
                    res.update(_resolve(defs[ref_key]))
            elif k == "anyOf":
                non_nulls = [_resolve(sub) for sub in v if not (isinstance(sub, dict) and sub.get("type") == "null")]
                if non_nulls:
                    first = non_nulls[0]
                    if isinstance(first, dict):
                        res.update(first)
            elif isinstance(v, dict):
                res[k] = _resolve(v)
            elif isinstance(v, list):
                res[k] = [_resolve(item) for item in v]
            else:
                res[k] = v
        res.pop("title", None)
        res.pop("additionalProperties", None)
        return res

    resolved_properties = {}
    for p_name, p_val in schema.get("properties", {}).items():
        resolved_properties[p_name] = _resolve(p_val)

    return {
        "type": "object",
        "properties": resolved_properties,
        "required": schema.get("required", []),
    }


class ToolRegistry:
    """In-memory registry of validated agent tools."""

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any] | None = None,
        input_model: type[BaseModel] | None = None,
        handler: Callable[[ToolContext, Any], Any] | None = None,
        is_read_only: bool = True,
        requires_confirmation: bool = False,
    ) -> ToolDefinition:
        """Register a tool with optional Pydantic input model and handler."""
        if input_model is not None and parameters is None:
            raw_schema = input_model.model_json_schema()
            parameters = dereference_schema(raw_schema)
        elif parameters is None:
            parameters = {"type": "object", "properties": {}}

        tool = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            input_model=input_model,
            handler=handler,
            is_read_only=is_read_only,
            requires_confirmation=requires_confirmation,
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

    def execute(
        self,
        name: str,
        context: ToolContext,
        raw_args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Validate model arguments and execute tool with trusted server context."""
        tool = self.get(name)
        if not tool:
            return {"error": f"Tool '{name}' is not registered."}
        if not tool.handler:
            return {"error": f"Tool '{name}' has no handler configured."}

        args_dict = raw_args or {}

        # 1. Pydantic schema validation
        if tool.input_model is not None:
            try:
                validated_args = tool.input_model.model_validate(args_dict)
            except ValidationError as exc:
                err_messages = [f"{e['loc']}: {e['msg']}" for e in exc.errors(include_url=False)]
                logger.warning("Tool %s validation failed: %s", name, err_messages)
                return {
                    "error": f"Invalid arguments for {name}",
                    "validation_errors": err_messages,
                }
            except Exception as exc:
                logger.warning("Tool %s argument parsing failed: %s", name, exc)
                return {"error": f"Failed to parse arguments for {name}: {str(exc)}"}
        else:
            validated_args = args_dict

        # 2. Execution with server-side context
        try:
            result = tool.handler(context, validated_args)
            if isinstance(result, dict):
                return result
            return {"result": result}
        except NotFoundError as exc:
            return {"error": f"{exc.resource_name} not found"}
        except ValueError as exc:
            return {"error": str(exc)}
        except Exception as exc:
            logger.exception("Unexpected error executing tool %s: %s", name, exc)
            return {"error": f"Internal error executing tool {name}"}


# Global tool registry instance ready for Phase 2 tool bindings
tool_registry = ToolRegistry()
