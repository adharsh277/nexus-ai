import logging
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
)

logger = logging.getLogger("nexus.llm.gemini")


class GeminiProvider(BaseLLMProvider):
    """Google Gemini LLM provider using the modern official google-genai SDK."""

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
        contents: list[types.Content] = []
        for msg in messages:
            # Map role: "user" -> "user", "assistant" -> "model"
            role = "user" if msg.role == "user" else "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg.content)],
                )
            )
        return contents

    def generate_reply(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Call Gemini to generate a response for the given conversation history."""
        if not messages:
            raise LLMError("Cannot generate reply for an empty message list")

        # Exclude system messages from the conversational turns and pass via config
        turn_messages = [m for m in messages if m.role in ("user", "assistant")]
        if not turn_messages:
            raise LLMError("At least one user message is required to generate a response")

        formatted_contents = self._format_messages(turn_messages)

        config_kwargs: dict[str, Any] = {
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
        }
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt

        config = types.GenerateContentConfig(**config_kwargs)

        try:
            logger.info("Calling Gemini model=%s with %d turns", self.model, len(formatted_contents))
            response = self.client.models.generate_content(
                model=self.model,
                contents=formatted_contents,
                config=config,
            )

            text = response.text or ""
            return LLMResponse(
                content=text.strip(),
                model=self.model,
                raw_response={"finish_reason": str(getattr(response, "candidates", [None])[0].finish_reason) if getattr(response, "candidates", None) else None},
            )

        except errors.APIError as exc:
            status_code = getattr(exc, "code", None)
            err_msg = str(exc)
            logger.warning("Gemini APIError code=%s: %s", status_code, type(exc).__name__)

            if status_code == 429 or "RESOURCE_EXHAUSTED" in err_msg or "rate limit" in err_msg.lower():
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

        except TimeoutError as exc:
            logger.warning("Gemini request timed out after %.1fs", self.timeout_seconds)
            raise LLMTimeoutError("Gemini request timed out. Please try again.") from exc

        except Exception as exc:
            logger.exception("Unexpected error during Gemini call: %s", type(exc).__name__)
            raise LLMError("An unexpected error occurred while generating AI response.") from exc
