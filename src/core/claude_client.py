"""Claude API client with retry logic, tool-use loop, and schema validation.

This module is the ONLY place in the codebase that talks to the Anthropic SDK.
All agents go through this layer.

Key features:
  - Exponential backoff retry (1s → 2s → 4s) for API failures
  - Schema validation loop: on Pydantic failure, re-prompts Claude with error (max 2 retries)
  - Full tool-use loop: handles multi-turn Claude tool_use → tool_result exchanges
  - Emits AgentTrace with full observability data
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Type, TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from src.core.model_router import ModelRouter, ModelTier, get_router
from src.tools.lookup_tools import TOOL_DEFINITIONS, dispatch_tool_call
from src.utils.logger import AgentTrace, ToolCallRecord, estimate_cost

T = TypeVar("T", bound=BaseModel)

# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
MAX_API_RETRIES = 3
MAX_SCHEMA_RETRIES = 2
BACKOFF_SECONDS = [1, 2, 4]
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "8192"))


class PipelineError(Exception):
    """Fatal pipeline error after exhausting all retries."""
    pass


@dataclass
class AgentResponse:
    """Typed return value from a ClaudeClient call."""

    content: str                          # raw text response from Claude
    parsed: Optional[BaseModel] = None   # Pydantic-validated output if schema provided
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tool_calls_made: list[ToolCallRecord] = field(default_factory=list)
    latency_ms: float = 0.0
    model: str = ""                       # actual model string used
    model_tier: str = ""                  # "sonnet" | "haiku"
    validation_retries: int = 0
    api_retries: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def cost_usd(self) -> float:
        return estimate_cost(self.prompt_tokens, self.completion_tokens, self.model)


class ClaudeClient:
    """Anthropic Claude API wrapper with smart model routing and full observability."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        router: Optional[ModelRouter] = None,
    ) -> None:
        resolved_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not resolved_key:
            raise PipelineError(
                "ANTHROPIC_API_KEY not set. Add it to .env or set the environment variable."
            )
        self._client = anthropic.Anthropic(api_key=resolved_key)
        self._router = router or get_router()
        # Expose the Sonnet model string as the default for display
        self.model = self._router.get_model(ModelTier.SONNET)

    # ── Public interface ──────────────────────────────────────────────────────

    def complete(
        self,
        system_prompt: str,
        user_message: str,
        *,
        agent_name: str = "unknown",
        iteration: int = 0,
        run_id: str = "",
        output_schema: Optional[Type[T]] = None,
        tools: Optional[list[str]] = None,
        temperature: float = 0.3,
        model_tier: ModelTier = ModelTier.SONNET,
    ) -> AgentResponse:
        """Run a Claude completion with smart model routing.

        Args:
            system_prompt: System instructions (authoritative; never from user input).
            user_message: The user turn content.
            agent_name: Name of the calling agent (for logging).
            iteration: Current pipeline iteration number.
            run_id: Current run ID.
            output_schema: If provided, parse and validate JSON response against this model.
            tools: List of tool names to enable (subset of TOOL_DEFINITIONS).
            temperature: Claude temperature (lower = more deterministic for structured output).
            model_tier: ModelTier.SONNET (default) or ModelTier.HAIKU.
                        Haiku is auto-selected for schema validation retries regardless.

        Returns:
            AgentResponse with content, parsed model, tokens, tool calls, latency.
        """
        selected_model = self._router.get_model(model_tier)
        start = time.monotonic()
        tool_calls_made: list[ToolCallRecord] = []
        api_retries = 0
        validation_retries = 0

        # Filter tool definitions to requested subset
        active_tools = self._filter_tools(tools)

        # ── API retry loop ────────────────────────────────────────────────────
        messages: list[dict] = [{"role": "user", "content": user_message}]

        for attempt in range(MAX_API_RETRIES):
            try:
                response, tool_calls_made = self._run_with_tool_loop(
                    system_prompt=system_prompt,
                    messages=messages,
                    active_tools=active_tools,
                    temperature=temperature,
                    model=selected_model,
                )
                break  # success
            except (
                anthropic.RateLimitError,
                anthropic.APIStatusError,
                anthropic.APIConnectionError,
            ) as exc:
                api_retries += 1
                if attempt == MAX_API_RETRIES - 1:
                    raise PipelineError(
                        f"[{agent_name}] API failed after {MAX_API_RETRIES} attempts: {exc}"
                    ) from exc
                wait = BACKOFF_SECONDS[attempt]
                time.sleep(wait)
        else:
            raise PipelineError(f"[{agent_name}] Exhausted API retry attempts.")

        # Extract usage and text
        prompt_tokens = response.usage.input_tokens
        completion_tokens = response.usage.output_tokens
        raw_text = self._extract_text(response)
        latency_ms = (time.monotonic() - start) * 1000

        # ── Schema validation loop ────────────────────────────────────────────
        parsed: Optional[BaseModel] = None
        if output_schema is not None:
            parsed, validation_retries, extra_tokens = self._validate_with_retry(
                raw_text=raw_text,
                schema=output_schema,
                system_prompt=system_prompt,
                original_user_message=user_message,
                active_tools=active_tools,
                temperature=temperature,
                agent_name=agent_name,
            )
            prompt_tokens += extra_tokens[0]
            completion_tokens += extra_tokens[1]

        return AgentResponse(
            content=raw_text,
            parsed=parsed,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            tool_calls_made=tool_calls_made,
            latency_ms=latency_ms,
            model=selected_model,
            model_tier=model_tier.value,
            validation_retries=validation_retries,
            api_retries=api_retries,
        )

    # ── Tool-use loop ─────────────────────────────────────────────────────────

    def _run_with_tool_loop(
        self,
        system_prompt: str,
        messages: list[dict],
        active_tools: list[dict],
        temperature: float,
        model: str,
    ) -> tuple[Any, list[ToolCallRecord]]:
        """Run Claude with multi-turn tool-use loop until a final text response."""
        tool_calls_made: list[ToolCallRecord] = []
        current_messages = list(messages)

        while True:
            kwargs: dict[str, Any] = {
                "model": model,
                "max_tokens": MAX_TOKENS,
                "system": system_prompt,
                "messages": current_messages,
                "temperature": temperature,
            }
            if active_tools:
                kwargs["tools"] = active_tools

            response = self._client.messages.create(**kwargs)

            # Check if Claude wants to call tools
            if response.stop_reason == "tool_use":
                # Process all tool calls in this response
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_input = block.input if isinstance(block.input, dict) else {}
                        tool_output = dispatch_tool_call(block.name, tool_input)
                        record = ToolCallRecord(
                            tool_name=block.name,
                            tool_input=tool_input,
                            tool_output=tool_output,
                        )
                        tool_calls_made.append(record)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(tool_output),
                        })

                # Append assistant turn + tool results to conversation
                current_messages.append({"role": "assistant", "content": response.content})
                current_messages.append({"role": "user", "content": tool_results})
                # Continue loop — Claude will now process tool results
                continue

            # Final text response
            return response, tool_calls_made

    # ── Schema validation with retry ─────────────────────────────────────────

    def _validate_with_retry(
        self,
        raw_text: str,
        schema: Type[T],
        system_prompt: str,
        original_user_message: str,
        active_tools: list[dict],
        temperature: float,
        agent_name: str,
    ) -> tuple[T, int, tuple[int, int]]:
        """Attempt to parse raw_text as schema. On failure, re-prompt with Haiku.

        Uses Haiku for retries — JSON fixing is a simple reformatting task.
        Returns (parsed_model, retry_count, (extra_prompt_tokens, extra_completion_tokens))
        """
        extra_prompt = 0
        extra_completion = 0
        # Haiku is sufficient (and cheaper) for JSON fix-up retries
        haiku_model = self._router.get_model(ModelTier.HAIKU)

        for attempt in range(MAX_SCHEMA_RETRIES + 1):
            try:
                json_str = self._extract_json(raw_text)
                data = json.loads(json_str)
                return schema(**data), attempt, (extra_prompt, extra_completion)
            except (ValidationError, json.JSONDecodeError, ValueError) as exc:
                if attempt == MAX_SCHEMA_RETRIES:
                    raise PipelineError(
                        f"[{agent_name}] Schema validation failed after {attempt} retries. "
                        f"Schema: {schema.__name__}. Last error: {exc}"
                    ) from exc

                # Re-prompt with Haiku (cheaper for simple JSON reformatting)
                error_msg = str(exc)
                retry_prompt = (
                    f"{original_user_message}\n\n"
                    f"---\n"
                    f"VALIDATION ERROR (attempt {attempt + 1}/{MAX_SCHEMA_RETRIES}):\n"
                    f"Your previous response could not be parsed as {schema.__name__}.\n"
                    f"Error: {error_msg}\n\n"
                    f"Please respond with ONLY valid JSON matching the schema. "
                    f"No markdown fences, no explanation — just the raw JSON object.\n"
                    f"Previous response:\n{raw_text[:2000]}"
                )

                retry_messages = [{"role": "user", "content": retry_prompt}]
                try:
                    retry_response, _ = self._run_with_tool_loop(
                        system_prompt=system_prompt,
                        messages=retry_messages,
                        active_tools=[],       # No tools on validation retry
                        temperature=0.1,       # Lower temp for deterministic JSON
                        model=haiku_model,     # ← Haiku: cheap JSON fix-up
                    )
                    extra_prompt += retry_response.usage.input_tokens
                    extra_completion += retry_response.usage.output_tokens
                    raw_text = self._extract_text(retry_response)
                except Exception:
                    continue

        raise PipelineError(f"[{agent_name}] Exhausted schema validation retries.")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _extract_text(self, response: Any) -> str:
        """Extract the text content from a Claude response."""
        texts = []
        for block in response.content:
            if hasattr(block, "text"):
                texts.append(block.text)
        return "\n".join(texts).strip()

    def _extract_json(self, text: str) -> str:
        """Extract JSON from text, stripping markdown code fences if present."""
        text = text.strip()
        # Remove ```json ... ``` or ``` ... ``` fences
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json or ```) and last line (```)
            inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            text = "\n".join(inner).strip()
        # Find first { or [ to locate JSON start
        for i, ch in enumerate(text):
            if ch in ("{", "["):
                text = text[i:]
                break
        return text

    def _filter_tools(self, tool_names: Optional[list[str]]) -> list[dict]:
        """Filter TOOL_DEFINITIONS to the requested subset."""
        if not tool_names:
            return []
        name_set = set(tool_names)
        return [t for t in TOOL_DEFINITIONS if t["name"] in name_set]
