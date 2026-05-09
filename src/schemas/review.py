"""Review schemas — output of the Review Agent.

Two distinct outputs:
  1. CritiqueOutput  — autonomous assessment of proposal quality
  2. TranslatedFeedback — structured translation of raw human feedback
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class IssueSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReviewRecommendation(str, Enum):
    APPROVE = "approve"
    REVISE = "revise"
    ESCALATE_TO_HUMAN = "escalate_to_human"


class CritiqueIssue(BaseModel):
    """A single identified issue in the proposal."""

    issue_id: str = Field(
        ...,
        description="Short snake_case identifier, e.g. 'budget_ambiguity'. "
        "Used for divergence tracking across iterations.",
    )
    location: str = Field(
        ...,
        description="Section or sub-section where the issue appears.",
    )
    severity: IssueSeverity = Field(..., description="Severity level of this issue.")
    description: str = Field(
        ...,
        min_length=20,
        description="Clear description of what is wrong or missing.",
    )
    fix_suggestion: str = Field(
        ...,
        min_length=20,
        description="Concrete suggestion for how to fix this issue.",
    )

    def fingerprint(self) -> str:
        """Stable fingerprint for divergence tracking."""
        return f"{self.issue_id}::{self.severity.value}"


class CritiqueOutput(BaseModel):
    """Full critique produced by the Review Agent."""

    issues: list[CritiqueIssue] = Field(
        default_factory=list,
        description="List of identified issues, ordered by severity (critical first).",
    )
    overall_score: int = Field(
        ...,
        ge=1,
        le=10,
        description="Overall proposal quality score from 1 (very poor) to 10 (ready to send).",
    )
    strengths: list[str] = Field(
        default_factory=list,
        description="What the proposal does well.",
    )
    recommendation: ReviewRecommendation = Field(
        ...,
        description="High-level recommendation for next step.",
    )
    reasoning: str = Field(
        ...,
        min_length=50,
        description="Explanation of the recommendation and score.",
    )
    iteration: int = Field(
        ...,
        ge=0,
        description="Pipeline iteration that produced this critique.",
    )

    @field_validator("issues")
    @classmethod
    def sort_issues_by_severity(cls, v: list[CritiqueIssue]) -> list[CritiqueIssue]:
        order = {
            IssueSeverity.CRITICAL: 0,
            IssueSeverity.HIGH: 1,
            IssueSeverity.MEDIUM: 2,
            IssueSeverity.LOW: 3,
        }
        return sorted(v, key=lambda i: order[i.severity])

    def has_critical_issues(self) -> bool:
        return any(i.severity == IssueSeverity.CRITICAL for i in self.issues)

    def issue_fingerprints(self) -> set[str]:
        return {i.fingerprint() for i in self.issues}

    def critical_and_high_count(self) -> int:
        return sum(
            1
            for i in self.issues
            if i.severity in (IssueSeverity.CRITICAL, IssueSeverity.HIGH)
        )


class FeedbackInstruction(BaseModel):
    """A single structured instruction derived from raw human feedback."""

    action: str = Field(
        ...,
        description="Imperative verb phrase describing what to do, e.g. 'Strengthen', 'Remove', 'Add'.",
    )
    target_section: str = Field(
        ...,
        description="Section of the proposal this instruction targets.",
    )
    detail: str = Field(
        ...,
        min_length=20,
        description="Specific, actionable detail about what change to make.",
    )
    priority: IssueSeverity = Field(
        ...,
        description="Priority level — determines ordering when Proposal Agent processes instructions.",
    )
    rationale: Optional[str] = Field(
        default=None,
        description="Why this change is needed (translated from human feedback context).",
    )


class TranslatedFeedback(BaseModel):
    """Structured translation of raw human feedback into actionable instructions."""

    raw_feedback: str = Field(
        ...,
        description="The original human feedback string (preserved verbatim).",
    )
    instructions: list[FeedbackInstruction] = Field(
        ...,
        min_length=1,
        description="Ordered list of structured instructions for the Proposal Agent. "
        "Never pass raw feedback directly.",
    )
    summary: str = Field(
        ...,
        min_length=20,
        description="One-sentence summary of what the human wants changed.",
    )
    iteration: int = Field(
        ...,
        ge=0,
        description="Pipeline iteration when this feedback was given.",
    )
    requires_matrix_revision: bool = Field(
        default=False,
        description="If True, the feedback implies the Debrief Matrix may need re-extraction.",
    )

    @field_validator("instructions")
    @classmethod
    def sort_by_priority(cls, v: list[FeedbackInstruction]) -> list[FeedbackInstruction]:
        order = {
            IssueSeverity.CRITICAL: 0,
            IssueSeverity.HIGH: 1,
            IssueSeverity.MEDIUM: 2,
            IssueSeverity.LOW: 3,
        }
        return sorted(v, key=lambda i: order[i.priority])
