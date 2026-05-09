"""Proposal Agent — generates a structured Markdown client proposal.

This agent:
  1. Receives the ClientMatrix from the Debrief Agent
  2. Optionally receives TranslatedFeedback from a previous iteration
  3. Calls the 'pricing_benchmark' tool via Claude tool-use API
  4. Returns a validated ProposalOutput (Markdown) with all required sections

Rules enforced:
  - Low/contradicted matrix items MUST appear in Open Questions, not as facts
  - Pricing must reference benchmark data from the tool call
  - No fabricated certainty where confidence is low or contradicted
"""

from __future__ import annotations

import json
from typing import Optional

from src.core.claude_client import ClaudeClient, AgentResponse
from src.schemas.matrix import ClientMatrix, ConfidenceLevel
from src.schemas.proposal import ProposalOutput
from src.schemas.review import TranslatedFeedback, IssueSeverity
from src.utils.logger import AgentTrace

# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are the Proposal Agent in a Client Proposal Pipeline system.

Your role: Generate a structured client proposal in Markdown using the provided Client Matrix.

## MANDATORY SECTIONS
Your proposal MUST include ALL of these sections (use these exact headings):

1. ## Executive Summary
2. ## Understanding
3. ## Approach
4. ## Phases & Timeline
5. ## Pricing Approach
6. ## Open Questions

## CRITICAL RULES
1. Items with confidence "low" or "contradicted" MUST appear in "Open Questions" — never state them as facts.
2. Items with confidence "high" or "medium" can be stated as facts.
3. Do NOT fabricate certainty. Preserve ambiguity where it exists.
4. The proposal must be professional, specific, and client-ready.
5. Reference the pricing benchmark data you retrieved via the pricing_benchmark tool.
6. Do NOT include internal matrix metadata in the proposal — translate insights into client-facing language.

## TOOL USAGE
Before writing the proposal, call the 'pricing_benchmark' tool with:
  - industry: "freight brokerage"
  - project_scope: "workflow automation and system integration"
  - duration_months: 6

Use the returned benchmark data to inform the Pricing Approach section.

## OUTPUT FORMAT
Respond with a JSON object:
{
  "version": <integer>,
  "iteration": <integer>,
  "content": "<full Markdown proposal as a JSON string>",
  "pricing_benchmark_used": "<one-line summary of the benchmark data used>"
}

The "content" field must be a valid JSON string containing the full Markdown proposal.
No additional fields. No explanation outside the JSON.
"""


class ProposalAgent:
    """Generates a structured client proposal using the Client Matrix."""

    def __init__(self, client: ClaudeClient) -> None:
        self._client = client

    def run(
        self,
        matrix: ClientMatrix,
        version: int,
        iteration: int,
        run_id: str = "",
        feedback: Optional[TranslatedFeedback] = None,
    ) -> tuple[ProposalOutput, AgentTrace]:
        """Run the Proposal Agent.

        Args:
            matrix: Validated ClientMatrix from the Debrief Agent.
            version: Version number for this proposal (increments each revision).
            iteration: Current pipeline iteration.
            run_id: Run ID for tracing.
            feedback: Structured feedback instructions from the Review Agent (if any).

        Returns:
            (ProposalOutput, AgentTrace)
        """
        user_message = self._build_user_message(matrix, version, iteration, feedback)

        response: AgentResponse = self._client.complete(
            system_prompt=_SYSTEM_PROMPT,
            user_message=user_message,
            agent_name="ProposalAgent",
            iteration=iteration,
            run_id=run_id,
            output_schema=ProposalOutput,
            tools=["pricing_benchmark"],
            temperature=0.4,
        )

        proposal: ProposalOutput = response.parsed

        trace = AgentTrace(
            run_id=run_id,
            agent="ProposalAgent",
            iteration=iteration,
            input_summary=(
                f"version={version}, "
                f"contradicted_items={len(matrix.get_contradicted_items())}, "
                f"feedback_instructions={len(feedback.instructions) if feedback else 0}"
            ),
            output_summary=(
                f"Proposal v{proposal.version} generated. "
                f"Words: {proposal.word_count()}. "
                f"Sections: {len(proposal.sections_present)}."
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

        return proposal, trace

    def _build_user_message(
        self,
        matrix: ClientMatrix,
        version: int,
        iteration: int,
        feedback: Optional[TranslatedFeedback],
    ) -> str:
        # Serialize the matrix as structured context
        matrix_json = json.dumps(matrix.model_dump(), indent=2)

        # Identify items that must go to Open Questions
        low_conf_items = matrix.get_low_confidence_items()
        open_q_items = []
        for dim, aspect, item in low_conf_items:
            open_q_items.append(
                f"- [{dim.upper()} / {aspect}] {item.statement} "
                f"(confidence: {item.confidence.value})"
                + (f" — {item.contradiction_note}" if item.contradiction_note else "")
            )
        open_q_summary = (
            "\n".join(open_q_items)
            if open_q_items
            else "None — all items have medium or high confidence."
        )

        feedback_section = ""
        if feedback:
            instructions_text = "\n".join(
                f"  {i+1}. [{inst.priority.value.upper()}] {inst.action} in '{inst.target_section}': {inst.detail}"
                for i, inst in enumerate(feedback.instructions)
            )
            feedback_section = (
                f"\n\n## REVISION INSTRUCTIONS (from human feedback)\n"
                f"Human feedback summary: {feedback.summary}\n\n"
                f"Apply these changes to your proposal (in priority order):\n"
                f"{instructions_text}\n"
                f"\nThis is revision {version} — please implement ALL instructions above."
            )

        return (
            f"Generate a client proposal (version {version}, iteration {iteration}).\n\n"
            f"## CLIENT MATRIX\n```json\n{matrix_json}\n```\n\n"
            f"## ITEMS THAT MUST GO TO OPEN QUESTIONS\n{open_q_summary}"
            f"{feedback_section}\n\n"
            f"Call the pricing_benchmark tool first, then write the proposal.\n"
            f"Respond with the JSON object as specified."
        )
