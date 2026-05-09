"""Pydantic schema definitions for inter-agent communication."""

from .matrix import (
    ConfidenceLevel,
    MatrixItem,
    MatrixDimension,
    ClientMatrix,
)
from .proposal import ProposalOutput
from .review import (
    IssueSeverity,
    CritiqueIssue,
    ReviewRecommendation,
    CritiqueOutput,
    FeedbackInstruction,
    TranslatedFeedback,
)

__all__ = [
    "ConfidenceLevel",
    "MatrixItem",
    "MatrixDimension",
    "ClientMatrix",
    "ProposalOutput",
    "IssueSeverity",
    "CritiqueIssue",
    "ReviewRecommendation",
    "CritiqueOutput",
    "FeedbackInstruction",
    "TranslatedFeedback",
]
