"""Review Agent — critiques proposals and translates human feedback.

This agent has TWO modes:

  1. critique(proposal, matrix, iteration)
     → Produces CritiqueOutput (structured issues + score + recommendation)

  2. translate_feedback(raw_feedback, proposal, critique, iteration)
     → Produces TranslatedFeedback (never passes raw text to Proposal Agent)
"""

from __future__ import annotations

import json
from typing import Optional

from src.core.claude_client import ClaudeClient, AgentResponse
from src.schemas.matrix import ClientMatrix
from src.schemas.proposal import ProposalOutput
from src.schemas.review import (
    CritiqueOutput,
    TranslatedFeedback,
)
from src.utils.logger import AgentTrace

# ── System prompts ────────────────────────────────────────────────────────────

_CRITIQUE_SYSTEM_PROMPT = """You are the Review Agent in a Client Proposal Pipeline system.

Your role: Critically evaluate a client proposal against the Client Matrix it was derived from.

## EVALUATION CRITERIA
Score the proposal (1-10) based on:
1. Factual accuracy vs. the Client Matrix
2. All required sections present (Executive Summary, Understanding, Approach, Phases, Pricing, Open Questions)
3. Low/contradicted items correctly placed in Open Questions (NOT stated as facts)
4. Pricing grounded in evidence (not arbitrary)
5. Tone: professional, specific, client-ready
6. Internal consistency (no contradictions within the proposal)
7. Addresses all major stakeholder concerns (Sarah, Marcus, Rita)

## SCORING GUIDE
- 9-10: Approve. Ready to send to client.
- 7-8: Minor issues. One revision round needed.
- 5-6: Significant issues. Multiple revisions likely.
- 1-4: Critical problems. Major rework required.

## RECOMMENDATION LOGIC
- overall_score >= 8 AND no critical/high issues → "approve"
- overall_score < 4 OR 3+ critical issues → "escalate_to_human"
- Otherwise → "revise"

## OUTPUT FORMAT
Respond with ONLY a JSON object:
{
  "issues": [
    {
      "issue_id": "snake_case_id",
      "location": "Section name or 'Global'",
      "severity": "critical|high|medium|low",
      "description": "What is wrong",
      "fix_suggestion": "How to fix it"
    }
  ],
  "overall_score": <1-10>,
  "strengths": ["strength 1", "strength 2"],
  "recommendation": "approve|revise|escalate_to_human",
  "reasoning": "Explanation of score and recommendation",
  "iteration": <integer>
}
"""

_TRANSLATE_SYSTEM_PROMPT = """You are the Review Agent in a Client Proposal Pipeline system.

Your role: Translate raw human feedback into structured, actionable instructions for the Proposal Agent.

## RULES
1. NEVER pass raw human feedback directly to the Proposal Agent.
2. Decompose vague feedback into specific, targeted instructions.
3. Each instruction must have: action (verb phrase), target_section, detail, priority.
4. If the feedback implies the underlying data (Client Matrix) is wrong, set requires_matrix_revision=true.
5. Be precise about WHAT to change and WHERE.

## OUTPUT FORMAT
Respond with ONLY a JSON object:
{
  "raw_feedback": "<verbatim human feedback>",
  "instructions": [
    {
      "action": "Imperative verb phrase",
      "target_section": "Section name",
      "detail": "Specific change to make",
      "priority": "critical|high|medium|low",
      "rationale": "Why this change is needed"
    }
  ],
  "summary": "One-sentence summary of what the human wants",
  "iteration": <integer>,
  "requires_matrix_revision": false
}
"""


class ReviewAgent:
    """Critiques proposals and translates human feedback into structured instructions."""

    def __init__(self, client: ClaudeClient) -> None:
        self._client = client

    def critique(
        self,
        proposal: ProposalOutput,
        matrix: ClientMatrix,
        iteration: int,
        run_id: str = "",
        previous_critiques: Optional[list[CritiqueOutput]] = None,
    ) -> tuple[CritiqueOutput, AgentTrace]:
        """Critique a proposal against the Client Matrix.

        Args:
            proposal: The proposal to critique.
            matrix: The source Client Matrix.
            iteration: Current pipeline iteration.
            run_id: Run ID for tracing.
            previous_critiques: Previous critiques (for context on repeated issues).

        Returns:
            (CritiqueOutput, AgentTrace)
        """
        user_message = self._build_critique_message(
            proposal, matrix, iteration, previous_critiques
        )

        response: AgentResponse = self._client.complete(
            system_prompt=_CRITIQUE_SYSTEM_PROMPT,
            user_message=user_message,
            agent_name="ReviewAgent.critique",
            iteration=iteration,
            run_id=run_id,
            output_schema=CritiqueOutput,
            tools=None,  # Review agent uses no tools — pure reasoning
            temperature=0.2,
        )

        critique: CritiqueOutput = response.parsed

        trace = AgentTrace(
            run_id=run_id,
            agent="ReviewAgent.critique",
            iteration=iteration,
            input_summary=(
                f"proposal_v{proposal.version}, words={proposal.word_count()}"
            ),
            output_summary=(
                f"Score={critique.overall_score}/10, "
                f"issues={len(critique.issues)} "
                f"({critique.critical_and_high_count()} critical/high), "
                f"recommendation={critique.recommendation.value}"
            ),
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            total_tokens=response.total_tokens,
            cost_usd=response.cost_usd,
            latency_ms=response.latency_ms,
            tool_calls=response.tool_calls_made,
            validation_retries=response.validation_retries,
            api_retries=response.api_retries,
            model=response.model,
            success=True,
        )

        return critique, trace

    def translate_feedback(
        self,
        raw_feedback: str,
        proposal: ProposalOutput,
        critique: CritiqueOutput,
        iteration: int,
        run_id: str = "",
    ) -> tuple[TranslatedFeedback, AgentTrace]:
        """Translate raw human feedback into structured Proposal Agent instructions.

        Args:
            raw_feedback: Raw text input from the human.
            proposal: The current proposal being revised.
            critique: The current critique (for context).
            iteration: Current pipeline iteration.
            run_id: Run ID for tracing.

        Returns:
            (TranslatedFeedback, AgentTrace)
        """
        user_message = self._build_translation_message(
            raw_feedback, proposal, critique, iteration
        )

        response: AgentResponse = self._client.complete(
            system_prompt=_TRANSLATE_SYSTEM_PROMPT,
            user_message=user_message,
            agent_name="ReviewAgent.translate",
            iteration=iteration,
            run_id=run_id,
            output_schema=TranslatedFeedback,
            tools=None,
            temperature=0.2,
        )

        translated: TranslatedFeedback = response.parsed

        trace = AgentTrace(
            run_id=run_id,
            agent="ReviewAgent.translate",
            iteration=iteration,
            input_summary=f"raw_feedback={len(raw_feedback)}c",
            output_summary=(
                f"Translated to {len(translated.instructions)} instructions. "
                f"Summary: {translated.summary}"
            ),
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            total_tokens=response.total_tokens,
            cost_usd=response.cost_usd,
            latency_ms=response.latency_ms,
            tool_calls=response.tool_calls_made,
            validation_retries=response.validation_retries,
            api_retries=response.api_retries,
            model=response.model,
            success=True,
        )

        return translated, trace

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_critique_message(
        self,
        proposal: ProposalOutput,
        matrix: ClientMatrix,
        iteration: int,
        previous_critiques: Optional[list[CritiqueOutput]],
    ) -> str:
        matrix_json = json.dumps(matrix.model_dump(), indent=2)
        contradicted = matrix.get_contradicted_items()
        low_conf = matrix.get_low_confidence_items()

        contradicted_summary = (
            "\n".join(
                f"  - [{dim}/{aspect}]: {item.statement} | note: {item.contradiction_note}"
                for dim, aspect, item in contradicted
            )
            or "  None"
        )
        low_conf_summary = (
            "\n".join(
                f"  - [{dim}/{aspect}]: {item.statement}"
                for dim, aspect, item in low_conf
            )
            or "  None"
        )

        prev_issues_text = ""
        if previous_critiques:
            prev_issues_text = "\n\n## ISSUES FROM PREVIOUS ITERATIONS (watch for recurrence)\n"
            for prev in previous_critiques[-2:]:
                for issue in prev.issues:
                    if issue.severity.value in ("critical", "high"):
                        prev_issues_text += (
                            f"  - [{issue.severity.value.upper()}] {issue.issue_id}: "
                            f"{issue.description}\n"
                        )

        return (
            f"Critique this proposal (version {proposal.version}, iteration {iteration}).\n\n"
            f"## PROPOSAL TO CRITIQUE\n{proposal.content}\n\n"
            f"## SOURCE CLIENT MATRIX\n```json\n{matrix_json}\n```\n\n"
            f"## CONTRADICTED ITEMS (must be in Open Questions)\n{contradicted_summary}\n\n"
            f"## LOW-CONFIDENCE ITEMS (must be in Open Questions)\n{low_conf_summary}"
            f"{prev_issues_text}\n\n"
            f"Set 'iteration' to {iteration} in your JSON response."
        )

    def _build_translation_message(
        self,
        raw_feedback: str,
        proposal: ProposalOutput,
        critique: CritiqueOutput,
        iteration: int,
    ) -> str:
        critique_summary = "\n".join(
            f"  - [{i.severity.value.upper()}] {i.location}: {i.description}"
            for i in critique.issues[:5]
        )

        return (
            f"Translate this human feedback into structured instructions "
            f"for the Proposal Agent (iteration {iteration}).\n\n"
            f"## RAW HUMAN FEEDBACK\n{raw_feedback}\n\n"
            f"## CURRENT PROPOSAL (version {proposal.version})\n"
            f"Sections: {', '.join(proposal.sections_present)}\n"
            f"Open Questions excerpt:\n{proposal.get_open_questions()[:500]}\n\n"
            f"## CURRENT CRITIQUE SUMMARY\n"
            f"Score: {critique.overall_score}/10\n"
            f"Top issues:\n{critique_summary}\n\n"
            f"Set 'raw_feedback' to the verbatim human feedback above.\n"
            f"Set 'iteration' to {iteration}.\n"
            f"Produce structured, actionable instructions — never pass raw feedback directly."
        )
