"""Centralized Eval Runner.

Runs both eval scripts programmatically (not via subprocess), captures all
results as structured data, and writes a timestamped Markdown report to:

    eval_logs/eval_report_YYYY-MM-DD_HH-MM-SS.md

Also writes a rolling eval_logs/latest.md for quick access.

Can be called:
  - Automatically after every pipeline run (from main.py)
  - Manually: python -m evals.eval_runner [--runs-dir runs/] [--run-id <id>]
"""

from __future__ import annotations

import argparse
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from evals.contradiction_recall_eval import (
    evaluate_run as contradiction_eval_run,
    ContradictionEvalResult,
    KNOWN_CONTRADICTIONS,
)
from evals.feedback_loop_regression_eval import (
    evaluate_run as feedback_eval_run,
    FeedbackLoopResult,
)
from src.core.state import RunState

EVAL_LOGS_DIR = Path(__file__).parent.parent / "eval_logs"


@dataclass
class SingleRunEvalReport:
    """All eval results for a single pipeline run."""

    run_id: str
    run_label: str
    run_status: str
    run_created_at: str
    run_iterations: int
    run_cost_usd: float
    final_score: Optional[int]

    contradiction_result: Optional[ContradictionEvalResult] = None
    contradiction_error: Optional[str] = None

    feedback_result: Optional[FeedbackLoopResult] = None
    feedback_error: Optional[str] = None

    @property
    def overall_passed(self) -> bool:
        c_ok = self.contradiction_result.passed if self.contradiction_result else False
        f_ok = self.feedback_result.passed if self.feedback_result else False
        return c_ok and f_ok

    @property
    def overall_grade(self) -> str:
        if self.overall_passed:
            return "✅ PASS"
        return "❌ FAIL"


@dataclass
class EvalSuiteReport:
    """Complete eval suite report across all evaluated runs."""

    triggered_at: str  # ISO 8601
    triggered_by: str  # "post_pipeline" | "manual" | "cli"
    runs_dir: str
    evaluated_run_ids: list[str]
    run_reports: list[SingleRunEvalReport] = field(default_factory=list)
    error_runs: list[tuple[str, str]] = field(default_factory=list)  # (run_id, error)

    @property
    def total_runs(self) -> int:
        return len(self.run_reports)

    @property
    def passed_runs(self) -> int:
        return sum(1 for r in self.run_reports if r.overall_passed)

    @property
    def suite_passed(self) -> bool:
        return self.passed_runs == self.total_runs and self.total_runs > 0

    @property
    def suite_grade(self) -> str:
        return "✅ ALL PASSED" if self.suite_passed else "❌ SOME FAILED"


def run_evals_for_run(run_id: str, runs_dir: Path) -> SingleRunEvalReport:
    """Run both evals for a single run and return a combined report."""
    # Load summary metadata
    try:
        state = RunState.load(run_id, runs_dir)
        critique = state.current_critique()
        report = SingleRunEvalReport(
            run_id=run_id,
            run_label=state.run_label,
            run_status=state.status,
            run_created_at=state.created_at,
            run_iterations=state.iteration,
            run_cost_usd=state.total_cost_usd,
            final_score=critique.overall_score if critique else None,
        )
    except Exception as e:
        # Minimal report if state can't be loaded
        report = SingleRunEvalReport(
            run_id=run_id,
            run_label="",
            run_status="unknown",
            run_created_at="",
            run_iterations=0,
            run_cost_usd=0.0,
            final_score=None,
            contradiction_error=f"Could not load RunState: {e}",
            feedback_error=f"Could not load RunState: {e}",
        )
        return report

    # Contradiction recall eval
    try:
        report.contradiction_result = contradiction_eval_run(run_id, runs_dir)
    except Exception as e:
        report.contradiction_error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    # Feedback loop regression eval
    try:
        report.feedback_result = feedback_eval_run(run_id, runs_dir)
    except Exception as e:
        report.feedback_error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    return report


def run_suite(
    runs_dir: Path,
    run_ids: Optional[list[str]] = None,
    triggered_by: str = "manual",
) -> EvalSuiteReport:
    """Run the full eval suite and return a structured report.

    Args:
        runs_dir: Path to the runs directory.
        run_ids: Specific run IDs to evaluate. If None, evaluates all runs.
        triggered_by: Label for what triggered the eval ('post_pipeline', 'manual', 'cli').

    Returns:
        EvalSuiteReport with all results.
    """
    if run_ids is None:
        run_ids = [
            d.name
            for d in sorted(runs_dir.iterdir())
            if d.is_dir() and (d / "state.json").exists()
        ]

    suite = EvalSuiteReport(
        triggered_at=datetime.now(timezone.utc).isoformat(),
        triggered_by=triggered_by,
        runs_dir=str(runs_dir),
        evaluated_run_ids=run_ids,
    )

    for run_id in run_ids:
        try:
            report = run_evals_for_run(run_id, runs_dir)
            suite.run_reports.append(report)
        except Exception as exc:
            suite.error_runs.append((run_id, str(exc)))

    return suite


def format_report_markdown(suite: EvalSuiteReport) -> str:
    """Format an EvalSuiteReport as a rich Markdown document."""
    now_local = datetime.now()
    timestamp_display = now_local.strftime("%Y-%m-%d %H:%M:%S")

    lines: list[str] = []

    # ── Header ────────────────────────────────────────────────────────────────
    lines += [
        "# Eval Suite Report",
        "",
        f"**Generated:** {timestamp_display}  ",
        f"**Triggered by:** `{suite.triggered_by}`  ",
        f"**Runs directory:** `{suite.runs_dir}`  ",
        f"**Runs evaluated:** {suite.total_runs}  ",
        f"**Overall result:** {suite.suite_grade}",
        "",
        "---",
        "",
    ]

    # ── Summary table ─────────────────────────────────────────────────────────
    lines += [
        "## Summary",
        "",
        "| Run ID | Label | Status | Iters | Cost | Final Score | Contradiction | Feedback Loop | Overall |",
        "|--------|-------|--------|-------|------|-------------|--------------|--------------|---------|",
    ]

    for r in suite.run_reports:
        c_grade = "—"
        if r.contradiction_result:
            c_grade = f"{'✅' if r.contradiction_result.passed else '❌'} P={r.contradiction_result.precision:.0%} R={r.contradiction_result.recall:.0%}"
        elif r.contradiction_error:
            c_grade = "⚠ ERROR"

        f_grade = "—"
        if r.feedback_result:
            f_grade = f"{'✅' if r.feedback_result.passed else '❌'} {r.feedback_result.score}"
        elif r.feedback_error:
            f_grade = "⚠ ERROR"

        score_str = f"{r.final_score}/10" if r.final_score else "—"
        cost_str = f"${r.run_cost_usd:.4f}"

        lines.append(
            f"| `{r.run_id}` | {r.run_label[:20]} | {r.run_status} | {r.run_iterations} "
            f"| {cost_str} | {score_str} | {c_grade} | {f_grade} | {r.overall_grade} |"
        )

    lines += ["", "---", ""]

    # ── Per-run detail ────────────────────────────────────────────────────────
    lines.append("## Per-Run Detail")
    lines.append("")

    for r in suite.run_reports:
        lines += [
            f"### Run `{r.run_id}` — {r.overall_grade}",
            "",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| Label | {r.run_label} |",
            f"| Status | `{r.run_status}` |",
            f"| Created | {r.run_created_at[:19]} |",
            f"| Iterations | {r.run_iterations} |",
            f"| Total Cost | ${r.run_cost_usd:.4f} |",
            f"| Final Review Score | {r.final_score}/10 |" if r.final_score else f"| Final Review Score | — |",
            "",
        ]

        # Contradiction eval detail
        lines.append("#### Contradiction Recall Eval")
        lines.append("")
        if r.contradiction_error:
            lines += [f"> ⚠ **ERROR:** `{r.contradiction_error[:300]}`", ""]
        elif r.contradiction_result:
            cr = r.contradiction_result
            lines += [
                f"**Result:** {'✅ PASS' if cr.passed else '❌ FAIL'}  ",
                f"**Precision:** {cr.precision:.1%}  ",
                f"**Recall:** {cr.recall:.1%}  ",
                f"**Matrix items total:** {cr.total_matrix_items}  ",
                f"**Contradicted items found:** {cr.contradicted_items_found}  ",
                f"**Contradiction notes present:** {cr.contradiction_notes_present}  ",
                "",
            ]
            if cr.known_contradictions_recalled:
                lines.append("**Known contradictions recalled:**")
                for cid in cr.known_contradictions_recalled:
                    lines.append(f"- ✓ `{cid}`")
                lines.append("")
            if cr.known_contradictions_missed:
                lines.append("**Missed contradictions:**")
                for cid in cr.known_contradictions_missed:
                    lines.append(f"- ✗ `{cid}`")
                lines.append("")
            if cr.contradiction_notes_missing:
                lines.append("**Notes missing at:**")
                for loc in cr.contradiction_notes_missing:
                    lines.append(f"- ✗ `{loc}`")
                lines.append("")

        # Feedback loop eval detail
        lines.append("#### Feedback Loop Regression Eval")
        lines.append("")
        if r.feedback_error:
            lines += [f"> ⚠ **ERROR:** `{r.feedback_error[:300]}`", ""]
        elif r.feedback_result:
            fl = r.feedback_result
            lines += [
                f"**Result:** {'✅ PASS' if fl.passed else '❌ FAIL'}  ",
                f"**Test Score:** {fl.score}  ",
                f"**Iterations checked:** {fl.iterations_checked}  ",
                "",
                "**Tests:**",
            ]
            for test_name, passed in fl.tests.items():
                icon = "✓" if passed else "✗"
                lines.append(f"- {icon} `{test_name}`")
            lines.append("")

            if fl.failures:
                lines.append("**Failures:**")
                for f_msg in fl.failures:
                    lines.append(f"- ❌ {f_msg}")
                lines.append("")
            if fl.warnings:
                lines.append("**Warnings:**")
                for w in fl.warnings:
                    lines.append(f"- ⚠ {w}")
                lines.append("")

        lines.append("---")
        lines.append("")

    # ── Error runs ────────────────────────────────────────────────────────────
    if suite.error_runs:
        lines += ["## Errored Runs", ""]
        for run_id, err in suite.error_runs:
            lines += [f"- **`{run_id}`**: {err}", ""]

    # ── Footer ────────────────────────────────────────────────────────────────
    lines += [
        "---",
        "",
        f"*Report generated by Client Proposal Pipeline eval suite.*  ",
        f"*UTC timestamp: {suite.triggered_at}*",
        "",
    ]

    return "\n".join(lines)


def save_report(suite: EvalSuiteReport, logs_dir: Path) -> Path:
    """Write the eval report to a timestamped file and update latest.md."""
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Timestamped filename
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_path = logs_dir / f"eval_report_{ts}.md"

    md = format_report_markdown(suite)
    report_path.write_text(md, encoding="utf-8")

    # Always update latest.md
    latest_path = logs_dir / "latest.md"
    latest_path.write_text(md, encoding="utf-8")

    return report_path


def print_suite_summary(suite: EvalSuiteReport) -> None:
    """Print a concise terminal summary of the eval suite."""
    sep = "═" * 60
    print(f"\n{sep}")
    print(f"  EVAL SUITE COMPLETE — {suite.suite_grade}")
    print(sep)
    print(f"  Triggered by:  {suite.triggered_by}")
    print(f"  Runs evaluated: {suite.total_runs}")
    print(f"  Passed:         {suite.passed_runs}/{suite.total_runs}")
    print()

    for r in suite.run_reports:
        c_str = "—"
        f_str = "—"
        if r.contradiction_result:
            c_str = f"{'PASS' if r.contradiction_result.passed else 'FAIL'} (P={r.contradiction_result.precision:.0%} R={r.contradiction_result.recall:.0%})"
        if r.feedback_result:
            f_str = f"{'PASS' if r.feedback_result.passed else 'FAIL'} ({r.feedback_result.score} tests)"

        overall_icon = "✅" if r.overall_passed else "❌"
        print(f"  {overall_icon} Run {r.run_id} ({r.run_label[:20]})")
        print(f"     Contradiction Recall:  {c_str}")
        print(f"     Feedback Loop:         {f_str}")
        print()

    if suite.error_runs:
        print(f"  ⚠  {len(suite.error_runs)} run(s) errored during eval:")
        for run_id, err in suite.error_runs:
            print(f"     • {run_id}: {err}")
        print()

    print(sep)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Eval Runner — runs both evals and saves a timestamped report."
    )
    parser.add_argument("--runs-dir", default="runs", help="Path to the runs directory.")
    parser.add_argument("--run-id", default=None, help="Evaluate a specific run ID only.")
    parser.add_argument(
        "--logs-dir",
        default="eval_logs",
        help="Directory to save eval report files (default: eval_logs/)",
    )
    args = parser.parse_args()

    runs_dir = Path(args.runs_dir)
    logs_dir = Path(args.logs_dir)

    if not runs_dir.exists():
        print(f"ERROR: runs directory not found: {runs_dir}")
        sys.exit(1)

    run_ids = [args.run_id] if args.run_id else None

    print(f"\n{'═' * 60}")
    print("  CLIENT PROPOSAL PIPELINE — EVAL RUNNER")
    print(f"{'═' * 60}")

    suite = run_suite(runs_dir=runs_dir, run_ids=run_ids, triggered_by="cli")

    if not suite.run_reports and not suite.error_runs:
        print("No runs found to evaluate. Run the pipeline first: python main.py")
        sys.exit(0)

    print_suite_summary(suite)
    report_path = save_report(suite, logs_dir)
    print(f"  📄 Report saved to: {report_path}")
    print(f"  📄 Latest report:   {logs_dir}/latest.md")
    print()

    sys.exit(0 if suite.suite_passed else 1)


if __name__ == "__main__":
    main()
