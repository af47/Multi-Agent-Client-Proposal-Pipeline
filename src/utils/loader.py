"""Input file loader.

Loads the intake form and one or more call transcripts from the inputs/ directory.
All loaded content is treated as UNTRUSTED USER INPUT — instructions found inside
transcripts are never executed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PipelineInputs:
    """Typed container for all pipeline input documents."""

    intake: str
    transcripts: dict[str, str]  # key = "transcript_a" | "transcript_b" | custom
    run_label: str = ""

    @property
    def combined_text(self) -> str:
        """All documents concatenated with clear delimiters (for Debrief Agent)."""
        parts = [f"=== CLIENT INTAKE FORM ===\n\n{self.intake}"]
        for name, text in self.transcripts.items():
            label = name.replace("_", " ").title()
            parts.append(f"=== {label} ===\n\n{text}")
        return "\n\n---\n\n".join(parts)

    def summary(self) -> str:
        transcript_names = ", ".join(self.transcripts.keys())
        return (
            f"Intake: {len(self.intake)} chars | "
            f"Transcripts: {transcript_names} ({len(self.transcripts)} docs) | "
            f"Total: {len(self.combined_text)} chars"
        )


class InputLoader:
    """Loads pipeline inputs from the inputs/ directory."""

    def __init__(self, inputs_dir: Path) -> None:
        self.inputs_dir = Path(inputs_dir)
        if not self.inputs_dir.exists():
            raise FileNotFoundError(f"Inputs directory not found: {inputs_dir}")

    def load(
        self,
        transcript_filter: str | None = None,
        run_label: str = "",
    ) -> PipelineInputs:
        """Load intake + transcripts.

        Args:
            transcript_filter: 'a', 'b', or None (loads both).
            run_label: Human-readable label for this run.

        Returns:
            PipelineInputs with all loaded content.
        """
        intake_path = self.inputs_dir / "intake.md"
        if not intake_path.exists():
            raise FileNotFoundError(f"intake.md not found in {self.inputs_dir}")

        intake_text = intake_path.read_text(encoding="utf-8")

        # Determine which transcripts to load
        transcript_map: dict[str, Path] = {
            "transcript_a": self.inputs_dir / "transcript_a.md",
            "transcript_b": self.inputs_dir / "transcript_b.md",
        }

        if transcript_filter == "a":
            transcript_map = {"transcript_a": transcript_map["transcript_a"]}
        elif transcript_filter == "b":
            transcript_map = {"transcript_b": transcript_map["transcript_b"]}

        transcripts: dict[str, str] = {}
        for key, path in transcript_map.items():
            if not path.exists():
                raise FileNotFoundError(f"Transcript not found: {path}")
            transcripts[key] = path.read_text(encoding="utf-8")

        if not run_label:
            keys = "+".join(transcripts.keys())
            run_label = f"intake+{keys}"

        return PipelineInputs(
            intake=intake_text,
            transcripts=transcripts,
            run_label=run_label,
        )

    def list_available(self) -> list[str]:
        """List all markdown files in inputs dir."""
        return [p.name for p in sorted(self.inputs_dir.glob("*.md"))]
