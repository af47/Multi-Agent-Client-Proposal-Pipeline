"""Proposal schema — output of the Proposal Agent.

The proposal is a structured Markdown document. We track versioning across
iterations so the full revision history is preserved in RunState.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ProposalOutput(BaseModel):
    """Structured output from the Proposal Agent."""

    version: int = Field(
        ...,
        ge=1,
        description="Proposal version number. Increments on each revision.",
    )
    iteration: int = Field(
        ...,
        ge=0,
        description="Pipeline iteration that produced this proposal.",
    )
    content: str = Field(
        ...,
        min_length=500,
        description="Full proposal as a Markdown string. Must include all required sections.",
    )
    sections_present: list[str] = Field(
        default_factory=list,
        description="List of section headers found in the proposal content.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of generation.",
    )
    model_used: Optional[str] = Field(
        default=None,
        description="Claude model identifier used to generate this proposal.",
    )
    pricing_benchmark_used: Optional[str] = Field(
        default=None,
        description="Pricing benchmark data injected via tool call (summary).",
    )

    REQUIRED_SECTIONS: list[str] = [
        "Executive Summary",
        "Understanding",
        "Approach",
        "Phases",
        "Pricing",
        "Open Questions",
    ]

    @field_validator("content")
    @classmethod
    def validate_required_sections(cls, v: str) -> str:
        """Enforce that all required sections are present in the proposal."""
        missing = []
        for section in cls.REQUIRED_SECTIONS:
            if section.lower() not in v.lower():
                missing.append(section)
        if missing:
            raise ValueError(
                f"Proposal is missing required sections: {missing}. "
                f"Every proposal MUST include: {cls.REQUIRED_SECTIONS}"
            )
        return v

    def model_post_init(self, __context) -> None:
        """Extract section headers from content after initialization."""
        if not self.sections_present:
            import re
            headers = re.findall(r"^#{1,3}\s+(.+)$", self.content, re.MULTILINE)
            self.sections_present = headers

    def word_count(self) -> int:
        return len(self.content.split())

    def get_open_questions(self) -> str:
        """Extract the Open Questions section from the proposal."""
        import re
        match = re.search(
            r"##\s*Open Questions\s*\n(.*?)(?=\n##|\Z)",
            self.content,
            re.DOTALL | re.IGNORECASE,
        )
        return match.group(1).strip() if match else ""
