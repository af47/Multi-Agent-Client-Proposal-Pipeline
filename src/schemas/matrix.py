"""4×4 Client Matrix schema — output of the Debrief Agent.

The matrix has 4 rows (dimensions) × 4 columns (aspects):
  Rows:    Business | Technical | Operational | Strategic
  Columns: pain_points | desired_state | success_criteria | risks_unknowns

Each cell is a MatrixItem that MUST preserve contradictions rather than resolve them.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    CONTRADICTED = "contradicted"


class MatrixItem(BaseModel):
    """A single cell in the 4×4 Client Matrix."""

    statement: str = Field(
        ...,
        min_length=10,
        description="1–2 sentence factual statement extracted from source material.",
    )
    confidence: ConfidenceLevel = Field(
        ...,
        description="Confidence level based on source clarity and consistency.",
    )
    source_excerpt: str = Field(
        ...,
        min_length=5,
        description="Verbatim quote from the intake or transcript that supports this item.",
    )
    contradiction_note: Optional[str] = Field(
        default=None,
        description="Required when confidence=='contradicted'. Describes the contradiction "
        "without resolving it.",
    )

    @model_validator(mode="after")
    def contradiction_requires_note(self) -> "MatrixItem":
        if self.confidence == ConfidenceLevel.CONTRADICTED and not self.contradiction_note:
            raise ValueError(
                "contradiction_note is required when confidence is 'contradicted'. "
                "Never resolve contradictions — preserve them explicitly."
            )
        return self


class MatrixDimension(BaseModel):
    """One row of the 4×4 matrix (one dimension of analysis)."""

    pain_points: MatrixItem = Field(
        ..., description="Current pain, problem, or friction in this dimension."
    )
    desired_state: MatrixItem = Field(
        ..., description="What the client wants / success looks like."
    )
    success_criteria: MatrixItem = Field(
        ..., description="Measurable criteria that would indicate success."
    )
    risks_unknowns: MatrixItem = Field(
        ..., description="Known risks, open questions, or unknowns in this dimension."
    )


class ClientMatrix(BaseModel):
    """The complete 4×4 Client Matrix produced by the Debrief Agent."""

    business: MatrixDimension = Field(
        ..., description="Business dimension: revenue, budget, commercial risk."
    )
    technical: MatrixDimension = Field(
        ..., description="Technical dimension: systems, integrations, architecture."
    )
    operational: MatrixDimension = Field(
        ..., description="Operational dimension: workflows, people, day-to-day process."
    )
    strategic: MatrixDimension = Field(
        ...,
        description="Strategic dimension: longer-term goals, competitive position, "
        "platform decisions.",
    )

    def get_contradicted_items(self) -> list[tuple[str, str, MatrixItem]]:
        """Return list of (dimension, aspect, item) for all contradicted items."""
        contradicted = []
        for dim_name in ("business", "technical", "operational", "strategic"):
            dim: MatrixDimension = getattr(self, dim_name)
            for aspect in ("pain_points", "desired_state", "success_criteria", "risks_unknowns"):
                item: MatrixItem = getattr(dim, aspect)
                if item.confidence == ConfidenceLevel.CONTRADICTED:
                    contradicted.append((dim_name, aspect, item))
        return contradicted

    def get_low_confidence_items(self) -> list[tuple[str, str, MatrixItem]]:
        """Return items with low or contradicted confidence (should go to Open Questions)."""
        low = []
        for dim_name in ("business", "technical", "operational", "strategic"):
            dim: MatrixDimension = getattr(self, dim_name)
            for aspect in ("pain_points", "desired_state", "success_criteria", "risks_unknowns"):
                item: MatrixItem = getattr(dim, aspect)
                if item.confidence in (ConfidenceLevel.LOW, ConfidenceLevel.CONTRADICTED):
                    low.append((dim_name, aspect, item))
        return low
