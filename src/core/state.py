"""Run state management and persistence.

RunState is the single source of truth for a pipeline execution.
It is serialized to /runs/<run_id>/ as JSON after each iteration,
enabling post-run inspection and resumption.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

from src.schemas.matrix import ClientMatrix
from src.schemas.proposal import ProposalOutput
from src.schemas.review import CritiqueOutput, TranslatedFeedback
from src.utils.logger import AgentTrace


RunStatus = Literal["running", "approved", "max_iterations", "diverged", "error"]


@dataclass
class RunState:
    """Complete state of a single pipeline run."""

    # Identity
    run_id: str
    input_hash: str          # SHA256 of combined input text
    run_label: str
    created_at: str          # ISO 8601 UTC

    # Pipeline outputs
    matrix: Optional[ClientMatrix] = None
    proposals: list[ProposalOutput] = field(default_factory=list)
    critiques: list[CritiqueOutput] = field(default_factory=list)
    feedback_history: list[str] = field(default_factory=list)   # raw human strings
    translated_feedbacks: list[TranslatedFeedback] = field(default_factory=list)

    # Control
    iteration: int = 0
    max_iterations: int = 5
    status: RunStatus = "running"
    final_proposal_version: Optional[int] = None

    # Observability
    traces: list[AgentTrace] = field(default_factory=list)
    total_cost_usd: float = 0.0
    total_tokens: int = 0

    # Divergence tracking: maps issue fingerprint → list of iteration numbers seen
    _issue_seen_iterations: dict[str, list[int]] = field(default_factory=dict)

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def new(
        cls,
        input_text: str,
        run_label: str = "",
        max_iterations: int = 5,
        run_id: Optional[str] = None,
    ) -> "RunState":
        run_id = run_id or str(uuid.uuid4())[:8]
        input_hash = hashlib.sha256(input_text.encode()).hexdigest()[:16]
        return cls(
            run_id=run_id,
            input_hash=input_hash,
            run_label=run_label,
            created_at=datetime.now(timezone.utc).isoformat(),
            max_iterations=max_iterations,
        )

    # ── Mutation helpers ──────────────────────────────────────────────────────

    def add_trace(self, trace: AgentTrace) -> None:
        self.traces.append(trace)
        self.total_cost_usd += trace.cost_usd
        self.total_tokens += trace.total_tokens

    def add_proposal(self, proposal: ProposalOutput) -> None:
        self.proposals.append(proposal)

    def add_critique(self, critique: CritiqueOutput) -> None:
        self.critiques.append(critique)
        # Update divergence tracking
        for fp in critique.issue_fingerprints():
            if fp not in self._issue_seen_iterations:
                self._issue_seen_iterations[fp] = []
            self._issue_seen_iterations[fp].append(self.iteration)

    def add_feedback(self, raw_feedback: str, translated: TranslatedFeedback) -> None:
        self.feedback_history.append(raw_feedback)
        self.translated_feedbacks.append(translated)

    def current_proposal(self) -> Optional[ProposalOutput]:
        return self.proposals[-1] if self.proposals else None

    def current_critique(self) -> Optional[CritiqueOutput]:
        return self.critiques[-1] if self.critiques else None

    def last_translated_feedback(self) -> Optional[TranslatedFeedback]:
        return self.translated_feedbacks[-1] if self.translated_feedbacks else None

    # ── Divergence detection ──────────────────────────────────────────────────

    def check_divergence(self) -> tuple[bool, str]:
        """Check if the pipeline should stop due to divergence.

        Returns (is_diverged, reason).

        Stops if:
          (A) Any single issue fingerprint has appeared in 3+ iterations.
          (B) Critique score has degraded > 2 points across last 3 consecutive iterations.
        """
        # Rule A: repeated critical/high issue
        for fp, iterations in self._issue_seen_iterations.items():
            if len(iterations) >= 3:
                return True, (
                    f"Divergence detected: issue '{fp}' has recurred in "
                    f"{len(iterations)} iterations ({iterations}). "
                    "Pipeline cannot resolve this automatically."
                )

        # Rule B: score degradation over last 3 critiques
        if len(self.critiques) >= 3:
            scores = [c.overall_score for c in self.critiques[-3:]]
            if scores[0] > scores[1] > scores[2] and (scores[0] - scores[2]) >= 2:
                return True, (
                    f"Divergence detected: proposal quality is degrading. "
                    f"Scores over last 3 iterations: {scores}."
                )

        return False, ""

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, runs_dir: Path) -> Path:
        """Serialize the full RunState to JSON."""
        run_dir = Path(runs_dir) / self.run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        state_dict = self._to_dict()
        state_path = run_dir / "metadata.json"
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state_dict, f, indent=2, default=str)

        if self.proposals:
            proposal_path = run_dir / "proposal.md"
            proposal_path.write_text(self.proposals[-1].content, encoding="utf-8")

        if self.matrix:
            matrix_path = run_dir / "matrix.json"
            with open(matrix_path, "w", encoding="utf-8") as f:
                json.dump(self.matrix.model_dump(), f, indent=2, default=str)

        if self.critiques:
            review_path = run_dir / "review.json"
            with open(review_path, "w", encoding="utf-8") as f:
                json.dump(self.critiques[-1].model_dump(), f, indent=2, default=str)

        # Write summary (optional but keeping for CLI display)
        summary_path = run_dir / "summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(self._summary_dict(), f, indent=2, default=str)

        return run_dir

    @classmethod
    def load(cls, run_id: str, runs_dir: Path) -> "RunState":
        """Load a RunState from disk."""
        state_path = Path(runs_dir) / run_id / "metadata.json"
        if not state_path.exists():
            raise FileNotFoundError(f"No saved run found: {state_path}")
        with open(state_path, encoding="utf-8") as f:
            data = json.load(f)
        return cls._from_dict(data)

    @classmethod
    def list_runs(cls, runs_dir: Path) -> list[dict]:
        """List all saved runs with their summaries."""
        runs_dir = Path(runs_dir)
        if not runs_dir.exists():
            return []
        results = []
        for run_dir in sorted(runs_dir.iterdir()):
            summary_path = run_dir / "summary.json"
            if summary_path.exists():
                with open(summary_path, encoding="utf-8") as f:
                    results.append(json.load(f))
        return results

    # ── Serialization ─────────────────────────────────────────────────────────

    def _to_dict(self) -> dict:
        """Convert RunState to a JSON-serializable dict."""
        return {
            "run_id": self.run_id,
            "input_hash": self.input_hash,
            "run_label": self.run_label,
            "created_at": self.created_at,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "status": self.status,
            "final_proposal_version": self.final_proposal_version,
            "total_cost_usd": self.total_cost_usd,
            "total_tokens": self.total_tokens,
            "matrix": self.matrix.model_dump() if self.matrix else None,
            "proposals": [p.model_dump() for p in self.proposals],
            "critiques": [c.model_dump() for c in self.critiques],
            "feedback_history": self.feedback_history,
            "translated_feedbacks": [t.model_dump() for t in self.translated_feedbacks],
            "traces": [t.to_dict() for t in self.traces],
            "_issue_seen_iterations": self._issue_seen_iterations,
        }

    @classmethod
    def _from_dict(cls, data: dict) -> "RunState":
        """Reconstruct RunState from a dict (loaded from JSON)."""
        state = cls(
            run_id=data["run_id"],
            input_hash=data["input_hash"],
            run_label=data.get("run_label", ""),
            created_at=data["created_at"],
            iteration=data.get("iteration", 0),
            max_iterations=data.get("max_iterations", 5),
            status=data.get("status", "running"),
            final_proposal_version=data.get("final_proposal_version"),
            total_cost_usd=data.get("total_cost_usd", 0.0),
            total_tokens=data.get("total_tokens", 0),
            _issue_seen_iterations=data.get("_issue_seen_iterations", {}),
        )

        if data.get("matrix"):
            state.matrix = ClientMatrix(**data["matrix"])

        state.proposals = [ProposalOutput(**p) for p in data.get("proposals", [])]
        state.critiques = [CritiqueOutput(**c) for c in data.get("critiques", [])]
        state.feedback_history = data.get("feedback_history", [])
        state.translated_feedbacks = [
            TranslatedFeedback(**t) for t in data.get("translated_feedbacks", [])
        ]
        state.traces = [AgentTrace.from_dict(t) for t in data.get("traces", [])]

        return state

    def _summary_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "run_label": self.run_label,
            "created_at": self.created_at,
            "status": self.status,
            "iteration": self.iteration,
            "proposals_count": len(self.proposals),
            "total_cost_usd": round(self.total_cost_usd, 4),
            "total_tokens": self.total_tokens,
            "final_score": (
                self.critiques[-1].overall_score if self.critiques else None
            ),
            "final_recommendation": (
                self.critiques[-1].recommendation.value if self.critiques else None
            ),
        }
