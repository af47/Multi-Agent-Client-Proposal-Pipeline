"""Structured observability logger for the pipeline.

Every agent call emits an AgentTrace that is:
  1. Written to Python logging (stdout + file)
  2. Stored in RunState.traces for post-run inspection
  3. Serializable to JSON for run persistence
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ── Cost estimation ─────────────────────────────────────────────────────────
# Delegated to ModelRouter so Haiku and Sonnet are priced correctly.
# Import lazily to avoid circular imports at module load time.


def estimate_cost(prompt_tokens: int, completion_tokens: int, model: str = "") -> float:
    """Estimate USD cost for a single Claude API call.

    Uses ModelRouter for per-model pricing (Haiku vs Sonnet).
    Falls back to Sonnet rates if model is unrecognised.
    """
    from src.core.model_router import estimate_cost_for_model  # lazy import
    return estimate_cost_for_model(model, prompt_tokens, completion_tokens)


@dataclass
class ToolCallRecord:
    """Record of a single tool invocation within an agent call."""

    tool_name: str
    tool_input: dict[str, Any]
    tool_output: Any
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AgentTrace:
    """Complete observability record for one agent invocation."""

    run_id: str
    agent: str
    iteration: int
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # I/O summaries (full content stored in RunState, not repeated here)
    input_summary: str = ""
    output_summary: str = ""

    # Token usage
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0

    # Latency
    latency_ms: float = 0.0

    # Tool calls
    tool_calls: list[ToolCallRecord] = field(default_factory=list)

    # Retry counts
    validation_retries: int = 0
    api_retries: int = 0

    # Model info — includes tier label for clarity in traces
    model: str = ""
    model_tier: str = ""   # "sonnet" | "haiku" | ""

    # Status
    success: bool = True
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "AgentTrace":
        tool_calls = [ToolCallRecord(**tc) for tc in d.pop("tool_calls", [])]
        return cls(tool_calls=tool_calls, **d)


class PipelineLogger:
    """Unified logger for the pipeline.

    Emits structured JSON log lines to a file and human-readable logs to stdout.
    """

    def __init__(self, run_id: str, log_dir: Path) -> None:
        self.run_id = run_id
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Human-readable logger (stdout)
        self._logger = logging.getLogger(f"pipeline.{run_id}")
        self._logger.setLevel(logging.DEBUG)

        if not self._logger.handlers:
            # Stdout handler
            ch = logging.StreamHandler(sys.stdout)
            ch.setLevel(logging.INFO)
            ch.setFormatter(
                logging.Formatter(
                    "%(asctime)s  %(levelname)-8s  %(message)s",
                    datefmt="%H:%M:%S",
                )
            )
            self._logger.addHandler(ch)

            # File handler (full debug)
            fh = logging.FileHandler(self.log_dir / "pipeline.log", encoding="utf-8")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(
                logging.Formatter(
                    "%(asctime)s  %(levelname)-8s  [%(name)s]  %(message)s"
                )
            )
            self._logger.addHandler(fh)

        # Structured JSON trace file
        self._trace_file = self.log_dir / "logs.json"

    # ── Public logging methods ────────────────────────────────────────────────

    def info(self, msg: str, **kwargs) -> None:
        self._logger.info(self._fmt(msg, **kwargs))

    def debug(self, msg: str, **kwargs) -> None:
        self._logger.debug(self._fmt(msg, **kwargs))

    def warning(self, msg: str, **kwargs) -> None:
        self._logger.warning(self._fmt(msg, **kwargs))

    def error(self, msg: str, **kwargs) -> None:
        self._logger.error(self._fmt(msg, **kwargs))

    def log_trace(self, trace: AgentTrace) -> None:
        """Write a structured AgentTrace to the JSONL trace file and emit summary log."""
        # Write JSON line
        with open(self._trace_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(trace.to_dict()) + "\n")

        # Emit human-readable summary
        status = "✓" if trace.success else "✗"
        tool_str = (
            f" | tools=[{', '.join(tc.tool_name for tc in trace.tool_calls)}]"
            if trace.tool_calls
            else ""
        )
        retry_str = ""
        if trace.validation_retries:
            retry_str += f" | val_retries={trace.validation_retries}"
        if trace.api_retries:
            retry_str += f" | api_retries={trace.api_retries}"

        self._logger.info(
            f"{status} [{trace.agent}] iter={trace.iteration} | "
            f"tokens={trace.total_tokens} ({trace.prompt_tokens}p+{trace.completion_tokens}c) | "
            f"cost=${trace.cost_usd:.4f} | "
            f"latency={trace.latency_ms:.0f}ms"
            f"{tool_str}{retry_str}"
        )

        if not trace.success:
            self._logger.error(f"  ↳ ERROR: {trace.error_message}")

    def log_agent_start(self, agent: str, iteration: int, input_summary: str) -> None:
        self._logger.info(
            f"▶ [{agent}] starting (iter={iteration}) | input={input_summary[:120]}"
        )

    def log_human_feedback(self, iteration: int, feedback: str) -> None:
        self._logger.info(
            f"👤 Human feedback (iter={iteration}): {feedback[:200]}"
        )

    def log_iteration_start(self, iteration: int, max_iterations: int) -> None:
        self._logger.info(
            f"\n{'─' * 60}\n"
            f"  ITERATION {iteration}/{max_iterations}\n"
            f"{'─' * 60}"
        )

    def log_pipeline_complete(self, status: str, run_id: str, total_cost: float) -> None:
        self._logger.info(
            f"\n{'═' * 60}\n"
            f"  PIPELINE COMPLETE  |  status={status}  |  run_id={run_id}\n"
            f"  total_cost=${total_cost:.4f}\n"
            f"{'═' * 60}"
        )

    def load_traces(self) -> list[AgentTrace]:
        """Load all traces from the JSONL file."""
        if not self._trace_file.exists():
            return []
        traces = []
        with open(self._trace_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    traces.append(AgentTrace.from_dict(json.loads(line)))
        return traces

    # ── Private helpers ───────────────────────────────────────────────────────

    def _fmt(self, msg: str, **kwargs) -> str:
        if kwargs:
            kv = " | ".join(f"{k}={v}" for k, v in kwargs.items())
            return f"{msg} | {kv}"
        return msg
