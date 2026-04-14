"""
LLM client — the single place all AI calls originate from.

Supports two providers, switchable via the LLM_PROVIDER env var:
  - "anthropic" (default) — Claude via the Anthropic SDK
      Prompt caching enabled on system prompts and large context blocks.
      Structured output via tool_use.
  - "gemini" — Gemini via the Google Generative AI SDK (free tier available)
      Structured output via JSON mode + response_schema.
      No explicit caching (handled server-side by Google).

mapper.py and planner.py call get_llm_client() and use call_structured() —
they are provider-agnostic.

Raw response content is never logged (documents may be confidential).
"""

import json
import logging
from pathlib import Path
from typing import Any, Protocol

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(filename: str) -> str:
    """Load a prompt template from the prompts/ directory."""
    path = _PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


# ── Shared interface ──────────────────────────────────────────────────────────

class LLMClient(Protocol):
    def call_structured(
        self,
        *,
        system_prompt_file: str,
        user_message: str,
        output_schema: dict[str, Any],
        tool_name: str,
        tool_description: str,
        extra_system_context: str = "",
    ) -> dict[str, Any]: ...


# ── Anthropic / Claude ────────────────────────────────────────────────────────

class AnthropicClient:
    """Claude via the Anthropic SDK. Prompt caching on all system context."""

    def __init__(self) -> None:
        import anthropic

        settings = get_settings()
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set in .env"
            )
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.claude_model

    def call_structured(
        self,
        *,
        system_prompt_file: str,
        user_message: str,
        output_schema: dict[str, Any],
        tool_name: str,
        tool_description: str,
        extra_system_context: str = "",
    ) -> dict[str, Any]:
        system_prompt = _load_prompt(system_prompt_file)

        # Both blocks cached — avoids re-encoding large schemas on every call
        system_blocks: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        if extra_system_context:
            system_blocks.append(
                {
                    "type": "text",
                    "text": extra_system_context,
                    "cache_control": {"type": "ephemeral"},
                }
            )

        logger.info(
            "Calling Anthropic model=%s tool=%s prompt=%s",
            self._model, tool_name, system_prompt_file,
        )

        response = self._client.messages.create(
            model=self._model,
            max_tokens=8192,
            system=system_blocks,
            tools=[
                {
                    "name": tool_name,
                    "description": tool_description,
                    "input_schema": output_schema,
                }
            ],
            tool_choice={"type": "tool", "name": tool_name},
            messages=[{"role": "user", "content": user_message}],
        )

        logger.info(
            "Anthropic response: stop_reason=%s usage=%s",
            response.stop_reason, response.usage,
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == tool_name:
                return block.input  # type: ignore[return-value]

        raise RuntimeError(
            f"Claude did not return a tool_use block for tool '{tool_name}'. "
            f"stop_reason={response.stop_reason}"
        )


# ── Google / Gemini ───────────────────────────────────────────────────────────

class GeminiClient:
    """
    Gemini via the Google Generative AI SDK.

    Uses JSON mode with response_schema for structured output — no function
    calling, so no proto-conversion complexity. The schema is passed directly
    to GenerationConfig; Gemini enforces it server-side.
    """

    def __init__(self) -> None:
        import google.generativeai as genai  # type: ignore[import-untyped]

        settings = get_settings()
        if not settings.gemini_api_key:
            raise RuntimeError(
                "LLM_PROVIDER=gemini but GEMINI_API_KEY is not set in .env"
            )
        genai.configure(api_key=settings.gemini_api_key)
        self._genai = genai
        self._model = settings.gemini_model

    def call_structured(
        self,
        *,
        system_prompt_file: str,
        user_message: str,
        output_schema: dict[str, Any],
        tool_name: str,
        tool_description: str,
        extra_system_context: str = "",
    ) -> dict[str, Any]:
        system_prompt = _load_prompt(system_prompt_file)

        # Gemini takes system instruction as a single string
        full_system = system_prompt
        if extra_system_context:
            full_system = f"{system_prompt}\n\n{extra_system_context}"

        model = self._genai.GenerativeModel(
            model_name=self._model,
            system_instruction=full_system,
            generation_config=self._genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=output_schema,
            ),
        )

        logger.info(
            "Calling Gemini model=%s tool=%s prompt=%s",
            self._model, tool_name, system_prompt_file,
        )

        response = model.generate_content(user_message)

        finish = (
            response.candidates[0].finish_reason
            if response.candidates
            else "unknown"
        )
        logger.info("Gemini response: finish_reason=%s", finish)

        if not response.text:
            raise RuntimeError(
                f"Gemini returned an empty response for tool '{tool_name}'. "
                f"finish_reason={finish}"
            )

        return json.loads(response.text)  # type: ignore[no-any-return]


# ── Factory ───────────────────────────────────────────────────────────────────

_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Return the configured LLM client. Instantiated once and reused."""
    global _client
    if _client is None:
        provider = get_settings().llm_provider.lower()
        if provider == "anthropic":
            _client = AnthropicClient()
        elif provider == "gemini":
            _client = GeminiClient()
        else:
            raise ValueError(
                f"Unknown LLM_PROVIDER='{provider}'. Must be 'anthropic' or 'gemini'."
            )
    return _client
