import logging
import uuid
from typing import Any

from google import genai
from google.genai import errors, types

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

logger = logging.getLogger("nexus.llm.gemini")


class GeminiProvider(BaseLLMProvider):
    """Google Gemini LLM provider using the modern official google-genai SDK."""

    supports_native_tools: bool = True

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        temperature: float = 0.7,
        max_output_tokens: int = 2048,
        timeout_seconds: float = 30.0,
    ):
        if not api_key:
            raise LLMAuthError("GEMINI_API_KEY is not configured in backend environment")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.timeout_seconds = timeout_seconds

        try:
            self.client = genai.Client(api_key=self.api_key)
        except Exception as exc:
            logger.error("Failed to initialize Google Gen AI client: %s", type(exc).__name__)
            raise LLMAuthError("Failed to initialize Gemini client with provided credentials") from exc

    def _format_messages(self, messages: list[LLMMessage]) -> list[types.Content]:
        """Convert standard LLMMessages into google-genai Content structures."""
        import json
        contents: list[types.Content] = []
        for msg in messages:
            if msg.role == "user":
                role = "user"
                part = types.Part.from_text(text=msg.content)
                contents.append(types.Content(role=role, parts=[part]))
            elif msg.role == "assistant":
                role = "model"
                parts = []
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        parts.append(types.Part.from_function_call(name=tc.name, args=tc.arguments))
                if msg.content:
                    parts.insert(0, types.Part.from_text(text=msg.content))
                if not parts:
                    parts.append(types.Part.from_text(text=""))
                contents.append(types.Content(role=role, parts=parts))
            elif msg.role == "tool":
                role = "user"
                try:
                    tool_data = json.loads(msg.content) if isinstance(msg.content, str) and (msg.content.startswith("{") or msg.content.startswith("[")) else {"result": msg.content}
                except Exception:
                    tool_data = {"result": msg.content}
                if not isinstance(tool_data, dict):
                    tool_data = {"result": tool_data}
                tool_name = msg.tool_name or "tool"
                part = types.Part.from_function_response(name=tool_name, response={"result": tool_data})
                contents.append(types.Content(role=role, parts=[part]))
            else:
                role = "user"
                part = types.Part.from_text(text=msg.content)
                contents.append(types.Content(role=role, parts=[part]))
        return contents

    def _build_native_tools(self, tools: list[dict[str, Any]]) -> list[types.Tool]:
        """Convert standard JSON schemas into google-genai native function declarations."""
        from app.services.llm.registry import dereference_schema
        declarations: list[types.FunctionDeclaration] = []
        for t in tools:
            name = t.get("name", "")
            desc = t.get("description", "")
            raw_params = t.get("parameters", {})
            clean_params = dereference_schema(raw_params)
            try:
                declarations.append(
                    types.FunctionDeclaration(
                        name=name,
                        description=desc,
                        parameters=clean_params,
                    )
                )
            except Exception as exc:
                logger.warning("Failed to build declaration for tool %s: %s", name, exc)
        return [types.Tool(function_declarations=declarations)]

    def generate_reply(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Call Gemini to generate a response, supporting native function calling if tools provided."""
        if not messages:
            raise LLMError("Cannot generate reply for an empty message list")

        turn_messages = [m for m in messages if m.role in ("user", "assistant", "tool")]
        if not turn_messages:
            raise LLMError("At least one conversational message is required to generate a response")

        formatted_contents = self._format_messages(turn_messages)

        config_kwargs: dict[str, Any] = {
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
        }
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt

        if tools:
            try:
                built_tools = self._build_native_tools(tools)
                if built_tools and built_tools[0].function_declarations:
                    config_kwargs["tools"] = built_tools
            except Exception as exc:
                logger.warning("Failed to build native Gemini tools, continuing without native tools: %s", exc)

        config = types.GenerateContentConfig(**config_kwargs)

        import time
        max_retries = 3
        try:
            for attempt in range(max_retries):
                try:
                    logger.info("Calling Gemini model=%s with %d turns (tools=%s, attempt=%d)", self.model, len(formatted_contents), bool(tools), attempt + 1)
                    response = self.client.models.generate_content(
                        model=self.model,
                        contents=formatted_contents,
                        config=config,
                    )

                    tool_calls: list[ToolCall] = []
                    text_parts: list[str] = []

                    # Check candidate parts for native function calls and text
                    if getattr(response, "candidates", None) and response.candidates:
                        candidate = response.candidates[0]
                        if getattr(candidate, "content", None) and getattr(candidate.content, "parts", None):
                            for part in candidate.content.parts:
                                fc = getattr(part, "function_call", None)
                                if fc and getattr(fc, "name", None):
                                    args = dict(fc.args or {}) if hasattr(fc, "args") else {}
                                    tool_calls.append(
                                        ToolCall(
                                            id=f"call_{fc.name}_{uuid.uuid4().hex[:6]}",
                                            name=fc.name,
                                            arguments=args,
                                        )
                                    )
                                txt = getattr(part, "text", None)
                                if txt:
                                    text_parts.append(txt)

                    # Fallback check on response.function_calls if present
                    if not tool_calls and getattr(response, "function_calls", None):
                        for fc in response.function_calls:
                            if getattr(fc, "name", None):
                                args = dict(fc.args or {}) if hasattr(fc, "args") else {}
                                tool_calls.append(
                                    ToolCall(
                                        id=f"call_{fc.name}_{uuid.uuid4().hex[:6]}",
                                        name=fc.name,
                                        arguments=args,
                                    )
                                )

                    text = "\n".join(text_parts).strip() if text_parts else (getattr(response, "text", "") or "").strip()
                    return LLMResponse(
                        content=text,
                        model=self.model,
                        tool_calls=tool_calls,
                        raw_response={
                            "finish_reason": str(getattr(response, "candidates", [None])[0].finish_reason)
                            if getattr(response, "candidates", None)
                            else None
                        },
                    )

                except errors.APIError as exc:
                    status_code = getattr(exc, "code", None)
                    err_msg = str(exc)
                    logger.warning("Gemini APIError code=%s: %s", status_code, type(exc).__name__)

                    if (status_code == 429 or "RESOURCE_EXHAUSTED" in err_msg or "rate limit" in err_msg.lower()):
                        if attempt < max_retries - 1:
                            sleep_time = 3.0 * (attempt + 1)
                            logger.warning("Gemini 429 rate limit hit, backoff sleeping %.1fs...", sleep_time)
                            time.sleep(sleep_time)
                            continue
                        raise LLMRateLimitError(
                            "Gemini API rate limit or quota exceeded. Please wait a moment and try again."
                        ) from exc
                    if status_code in (401, 403) or "PERMISSION_DENIED" in err_msg or "UNAUTHENTICATED" in err_msg or "API_KEY_INVALID" in err_msg:
                        raise LLMAuthError("Invalid or unauthorized Gemini API key.") from exc
                    if status_code in (503, 504) or "UNAVAILABLE" in err_msg or "DEADLINE_EXCEEDED" in err_msg:
                        raise LLMUnavailableError(
                            "Gemini service is temporarily unavailable. Please retry shortly."
                        ) from exc
                    raise LLMError("Gemini service encountered an error processing your request.") from exc

            raise LLMRateLimitError("Gemini API rate limit exceeded after multiple retries.")

        except TimeoutError as exc:
            logger.warning("Gemini request timed out after %.1fs", self.timeout_seconds)
            raise LLMTimeoutError("Gemini request timed out. Please try again.") from exc

        except (LLMError, LLMRateLimitError, LLMAuthError, LLMUnavailableError, LLMTimeoutError):
            raise

        except Exception as exc:
            logger.exception("Unexpected error during Gemini call: %s", type(exc).__name__)
            raise LLMError("An unexpected error occurred while generating AI response.") from exc
