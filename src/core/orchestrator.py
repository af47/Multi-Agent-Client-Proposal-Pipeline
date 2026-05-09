"""Pipeline Orchestrator — manages the full Debrief → Proposal → Review loop.

This is the top-level coordination layer. Agents never call each other directly;
all inter-agent communication flows through the orchestrator via typed schemas.

Flow:
  1. DebriefAgent → ClientMatrix
  2. Loop (max_iterations):
     a. ProposalAgent → ProposalOutput
     b. ReviewAgent.critique → CritiqueOutput
     c. Divergence check
     d. If approve → done
     e. Human feedback (CLI or auto-approve)
     f. ReviewAgent.translate_feedback → TranslatedFeedback
     g. Increment iteration
  3. Save RunState
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional, Callable

from src.agents.debrief_agent import DebriefAgent
from src.agents.proposal_agent import ProposalAgent
from src.agents.review_agent import ReviewAgent
from src.core.claude_client import ClaudeClient, PipelineError
from src.core.state import RunState
from src.schemas.review import ReviewRecommendation
from src.utils.loader import PipelineInputs
from src.utils.logger import PipelineLogger

_RUNS_DIR = Path(__file__).parent.parent.parent / "runs"


class PipelineOrchestrator:
    """Orchestrates the full 3-agent Client Proposal Pipeline."""

    def __init__(
        self,
        client: ClaudeClient,
        runs_dir: Path = _RUNS_DIR,
        max_iterations: int = 5,
        non_interactive: bool = False,
        feedback_provider: Optional[Callable[[str, str, int], str]] = None,
    ) -> None:
        """
        Args:
            client: Configured ClaudeClient instance.
            runs_dir: Directory to persist run state.
            max_iterations: Maximum proposal revision iterations.
            non_interactive: If True, auto-approve after first iteration (for CI/eval).
            feedback_provider: Optional callable for custom feedback injection.
                               Signature: (proposal_content, critique_summary, iteration) → str.
                               If None and not non_interactive, reads from stdin.
        """
        self._client = client
        self._runs_dir = Path(runs_dir)
        self._max_iterations = max_iterations
        self._non_interactive = non_interactive
        self._feedback_provider = feedback_provider

        # Agents
        self._debrief = DebriefAgent(client)
        self._proposal = ProposalAgent(client)
        self._review = ReviewAgent(client)

    def run(self, inputs: PipelineInputs, run_id: Optional[str] = None) -> RunState:
        """Execute the full pipeline from inputs to final proposal.

        Args:
            inputs: Loaded PipelineInputs (intake + transcripts).
            run_id: Explicit ID for the run (e.g., transcript name). If None, generates UUID.

        Returns:
            Finalized RunState with all artifacts and traces.
        """
        # Initialize state
        state = RunState.new(
            input_text=inputs.combined_text,
            run_label=inputs.run_label,
            max_iterations=self._max_iterations,
            run_id=run_id,
        )
        logger = PipelineLogger(state.run_id, self._runs_dir / state.run_id)

        logger.info(
            f"Pipeline starting",
            run_id=state.run_id,
            label=state.run_label,
            inputs=inputs.summary(),
        )

        try:
            # ── Phase 1: Debrief ─────────────────────────────────────────────
            logger.log_agent_start("DebriefAgent", 0, inputs.summary())
            matrix, debrief_trace = self._debrief.run(
                inputs=inputs,
                run_id=state.run_id,
                iteration=0,
            )
            state.matrix = matrix
            state.add_trace(debrief_trace)
            logger.log_trace(debrief_trace)
            logger.info(
                f"Matrix extracted",
                contradicted={len(matrix.get_contradicted_items())},
                low_confidence={len(matrix.get_low_confidence_items())},
            )

            # Save after debrief
            state.save(self._runs_dir)

            # ── Phase 2: Proposal → Review loop ─────────────────────────────
            for iteration in range(1, self._max_iterations + 1):
                state.iteration = iteration
                logger.log_iteration_start(iteration, self._max_iterations)

                feedback = state.last_translated_feedback()

                # Proposal Agent
                logger.log_agent_start(
                    "ProposalAgent",
                    iteration,
                    f"version={len(state.proposals) + 1}",
                )
                proposal, proposal_trace = self._proposal.run(
                    matrix=matrix,
                    version=len(state.proposals) + 1,
                    iteration=iteration,
                    run_id=state.run_id,
                    feedback=feedback,
                )
                state.add_proposal(proposal)
                state.add_trace(proposal_trace)
                logger.log_trace(proposal_trace)

                # Review Agent — critique
                logger.log_agent_start("ReviewAgent.critique", iteration, f"proposal_v{proposal.version}")
                critique, critique_trace = self._review.critique(
                    proposal=proposal,
                    matrix=matrix,
                    iteration=iteration,
                    run_id=state.run_id,
                    previous_critiques=state.critiques[:-1] if state.critiques else None,
                )
                state.add_critique(critique)
                state.add_trace(critique_trace)
                logger.log_trace(critique_trace)

                # Save after each iteration
                state.save(self._runs_dir)

                # Display critique to user
                self._display_critique(critique, iteration, logger)

                # Check for approval
                if critique.recommendation == ReviewRecommendation.APPROVE:
                    logger.info("✅ Proposal approved by Review Agent.")
                    state.status = "approved"
                    state.final_proposal_version = proposal.version
                    break

                # Check for divergence
                is_diverged, divergence_reason = state.check_divergence()
                if is_diverged:
                    logger.warning(f"⚠️  Divergence detected: {divergence_reason}")
                    state.status = "diverged"
                    break

                # Check max iterations
                if iteration == self._max_iterations:
                    logger.warning("⚠️  Max iterations reached without approval.")
                    state.status = "max_iterations"
                    break

                # Escalation
                if critique.recommendation == ReviewRecommendation.ESCALATE_TO_HUMAN:
                    logger.warning(
                        "⚠️  Review Agent recommends escalation to human. "
                        "Pausing for feedback."
                    )

                # ── Human-in-the-loop ────────────────────────────────────────
                raw_feedback = self._get_human_feedback(
                    proposal=proposal,
                    critique=critique,
                    iteration=iteration,
                    logger=logger,
                )

                if raw_feedback.strip().lower() in ("approve", "approved", "ok", "lgtm"):
                    logger.info("✅ Human approved the proposal.")
                    state.status = "approved"
                    state.final_proposal_version = proposal.version
                    break

                logger.log_human_feedback(iteration, raw_feedback)

                # Review Agent — translate feedback
                logger.log_agent_start("ReviewAgent.translate", iteration, f"feedback={len(raw_feedback)}c")
                translated, translate_trace = self._review.translate_feedback(
                    raw_feedback=raw_feedback,
                    proposal=proposal,
                    critique=critique,
                    iteration=iteration,
                    run_id=state.run_id,
                )
                state.add_feedback(raw_feedback, translated)
                state.add_trace(translate_trace)
                logger.log_trace(translate_trace)

                logger.info(
                    f"Feedback translated to {len(translated.instructions)} instructions. "
                    f"Summary: {translated.summary}"
                )

                # Save after feedback translation
                state.save(self._runs_dir)

            # Final save
            if state.status == "running":
                state.status = "max_iterations"
            final_dir = state.save(self._runs_dir)

            logger.log_pipeline_complete(
                status=state.status,
                run_id=state.run_id,
                total_cost=state.total_cost_usd,
            )
            logger.info(f"Run saved to: {final_dir}")

        except PipelineError as exc:
            state.status = "error"
            logger.error(f"Pipeline error: {exc}")
            state.save(self._runs_dir)
            raise

        return state

    def resume(self, run_id: str, inputs: PipelineInputs) -> RunState:
        """Resume a previously saved run from where it left off.

        Loads the saved RunState and continues the loop from the current iteration.
        """
        state = RunState.load(run_id, self._runs_dir)
        logger = PipelineLogger(state.run_id, self._runs_dir / state.run_id)
        logger.info(f"Resuming run {run_id} at iteration {state.iteration}")

        if state.status != "running":
            logger.warning(f"Run {run_id} has status '{state.status}' — nothing to resume.")
            return state

        # Reassign matrix and continue from current iteration
        # (Matrix is preserved; re-use existing proposals list length)
        matrix = state.matrix
        if matrix is None:
            raise PipelineError(f"Cannot resume run {run_id}: matrix is missing.")

        # Continue the loop
        for iteration in range(state.iteration + 1, self._max_iterations + 1):
            state.iteration = iteration
            logger.log_iteration_start(iteration, self._max_iterations)
            feedback = state.last_translated_feedback()

            proposal, proposal_trace = self._proposal.run(
                matrix=matrix,
                version=len(state.proposals) + 1,
                iteration=iteration,
                run_id=state.run_id,
                feedback=feedback,
            )
            state.add_proposal(proposal)
            state.add_trace(proposal_trace)
            logger.log_trace(proposal_trace)

            critique, critique_trace = self._review.critique(
                proposal=proposal,
                matrix=matrix,
                iteration=iteration,
                run_id=state.run_id,
                previous_critiques=state.critiques[:-1] if state.critiques else None,
            )
            state.add_critique(critique)
            state.add_trace(critique_trace)
            logger.log_trace(critique_trace)
            state.save(self._runs_dir)
            self._display_critique(critique, iteration, logger)

            if critique.recommendation == ReviewRecommendation.APPROVE:
                state.status = "approved"
                state.final_proposal_version = proposal.version
                break

            is_diverged, reason = state.check_divergence()
            if is_diverged:
                state.status = "diverged"
                logger.warning(reason)
                break

            if iteration == self._max_iterations:
                state.status = "max_iterations"
                break

            raw_feedback = self._get_human_feedback(proposal, critique, iteration, logger)
            if raw_feedback.strip().lower() in ("approve", "approved", "ok", "lgtm"):
                state.status = "approved"
                state.final_proposal_version = proposal.version
                break

            logger.log_human_feedback(iteration, raw_feedback)
            translated, translate_trace = self._review.translate_feedback(
                raw_feedback=raw_feedback,
                proposal=proposal,
                critique=critique,
                iteration=iteration,
                run_id=state.run_id,
            )
            state.add_feedback(raw_feedback, translated)
            state.add_trace(translate_trace)
            logger.log_trace(translate_trace)
            state.save(self._runs_dir)

        if state.status == "running":
            state.status = "max_iterations"
        state.save(self._runs_dir)
        logger.log_pipeline_complete(state.status, state.run_id, state.total_cost_usd)
        return state

    # ── Private helpers ───────────────────────────────────────────────────────

    def _display_critique(self, critique, iteration: int, logger: PipelineLogger) -> None:
        """Print a formatted critique summary to stdout."""
        separator = "─" * 60
        lines = [
            f"\n{separator}",
            f"  REVIEW AGENT CRITIQUE  (Iteration {iteration})",
            separator,
            f"  Score: {critique.overall_score}/10",
            f"  Recommendation: {critique.recommendation.value.upper()}",
            f"  Reasoning: {critique.reasoning}",
        ]
        if critique.strengths:
            lines.append(f"\n  Strengths:")
            for s in critique.strengths:
                lines.append(f"    ✓ {s}")
        if critique.issues:
            lines.append(f"\n  Issues ({len(critique.issues)}):")
            for issue in critique.issues:
                lines.append(
                    f"    [{issue.severity.value.upper()}] {issue.location} — "
                    f"{issue.description}"
                )
                lines.append(f"      → Fix: {issue.fix_suggestion}")
        lines.append(separator)
        print("\n".join(lines))

    def _get_human_feedback(
        self,
        proposal,
        critique,
        iteration: int,
        logger: PipelineLogger,
    ) -> str:
        """Get feedback from human (CLI, callback, or auto-approve)."""
        if self._non_interactive:
            # Auto-approve in non-interactive mode
            logger.info("Non-interactive mode: auto-approving proposal.")
            return "approve"

        if self._feedback_provider is not None:
            # Use injected feedback provider (for testing / eval)
            critique_summary = f"Score={critique.overall_score}/10. Issues: " + "; ".join(
                f"{i.severity.value}: {i.description}" for i in critique.issues[:3]
            )
            return self._feedback_provider(proposal.content, critique_summary, iteration)

        # Interactive CLI
        print(
            f"\n{'─' * 60}\n"
            f"  HUMAN FEEDBACK REQUIRED  (Iteration {iteration})\n"
            f"{'─' * 60}\n"
            f"  The proposal is saved at: runs/{proposal.version}/latest_proposal.md\n"
            f"\n  Options:\n"
            f"    • Type your feedback to request changes\n"
            f"    • Type 'approve' / 'ok' / 'lgtm' to accept\n"
            f"    • Type 'quit' to abort the pipeline\n"
            f"{'─' * 60}\n"
        )

        try:
            feedback = input("Your feedback: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nPipeline interrupted by user.")
            sys.exit(0)

        if feedback.lower() == "quit":
            print("Pipeline aborted by user.")
            sys.exit(0)

        return feedback
