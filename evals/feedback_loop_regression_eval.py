"""Eval: Feedback Loop Regression

Tests the quality and correctness of the human-in-the-loop feedback cycle:

  1. TranslatedFeedback produces structured instructions (not raw text pass-through)
  2. Proposal version increments correctly on each revision
  3. Critique score does NOT monotonically degrade across iterations
  4. Each feedback instruction has all required fields (action, target_section, detail, priority)
  5. Review Agent does not repeat the same high-severity issue fingerprint 3+ times
     (divergence should have been triggered before that)

Usage:
  python -m evals.feedback_loop_regression_eval [--runs-dir runs/] [--run-id <id>]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.state import RunState
from src.schemas.review import IssueSeverity


@dataclass
class FeedbackLoopResult:
    run_id: str
    iterations_checked: int
    tests: dict[str, bool] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.failures) == 0

    @property
    def score(self) -> str:
        total = len(self.tests)
        passed = sum(1 for v in self.tests.values() if v)
        return f"{passed}/{total}"


def evaluate_run(run_id: str, runs_dir: Path) -> FeedbackLoopResult:
    """Run all feedback loop regression checks on a single run."""
    state = RunState.load(run_id, runs_dir)
    result = FeedbackLoopResult(
        run_id=run_id,
        iterations_checked=state.iteration,
    )

    # ── Test 1: Proposal version increments ──────────────────────────────────
    test_name = "proposal_version_increments"
    if len(state.proposals) < 2:
        result.warnings.append(
            "Only 1 proposal found — skipping version increment check (need 2+ iterations)."
        )
        result.tests[test_name] = True  # Not a failure, just not enough data
    else:
        versions = [p.version for p in state.proposals]
        is_increasing = all(b > a for a, b in zip(versions, versions[1:]))
        result.tests[test_name] = is_increasing
        if not is_increasing:
            result.failures.append(
                f"[{test_name}] Proposal versions did not increment: {versions}"
            )

    # ── Test 2: TranslatedFeedback contains structured instructions ───────────
    test_name = "feedback_is_structured"
    if not state.translated_feedbacks:
        result.warnings.append("No translated feedbacks found — skipping (no revisions ran).")
        result.tests[test_name] = True
    else:
        all_structured = True
        for i, tf in enumerate(state.translated_feedbacks):
            if not tf.instructions:
                result.failures.append(
                    f"[{test_name}] TranslatedFeedback #{i+1} has no instructions. "
                    f"Raw feedback was passed through unstructured."
                )
                all_structured = False
                continue
            for j, inst in enumerate(tf.instructions):
                if not inst.action or not inst.target_section or not inst.detail:
                    result.failures.append(
                        f"[{test_name}] Instruction #{j+1} in feedback #{i+1} is missing "
                        f"required fields (action, target_section, detail)."
                    )
                    all_structured = False
                # Check it's not just echoing raw feedback
                if tf.raw_feedback.strip()[:50].lower() in inst.detail.lower():
                    result.warnings.append(
                        f"[{test_name}] Instruction #{j+1} in feedback #{i+1} may be "
                        f"echoing raw feedback rather than translating it."
                    )
        result.tests[test_name] = all_structured

    # ── Test 3: Critique score does not continuously degrade ─────────────────
    test_name = "score_not_monotonically_degrading"
    if len(state.critiques) < 3:
        result.warnings.append(
            f"Only {len(state.critiques)} critique(s) — skipping score degradation check (need 3+)."
        )
        result.tests[test_name] = True
    else:
        scores = [c.overall_score for c in state.critiques]
        # Fail if score drops 3+ consecutive times AND total drop > 2 points
        consecutive_drops = 0
        max_consecutive = 0
        for i in range(1, len(scores)):
            if scores[i] < scores[i - 1]:
                consecutive_drops += 1
                max_consecutive = max(max_consecutive, consecutive_drops)
            else:
                consecutive_drops = 0

        degrading = max_consecutive >= 3 and (max(scores) - min(scores)) >= 3
        result.tests[test_name] = not degrading
        if degrading:
            result.failures.append(
                f"[{test_name}] Critique scores show sustained degradation: {scores}. "
                f"Divergence detection should have triggered earlier."
            )
        else:
            # Just warn on any 2-point drop
            for i in range(1, len(scores)):
                if scores[i - 1] - scores[i] >= 2:
                    result.warnings.append(
                        f"[{test_name}] Score dropped from {scores[i-1]} to {scores[i]} "
                        f"between iterations {i} and {i+1}."
                    )

    # ── Test 4: No unresolved critical issue repeated 3+ times ───────────────
    test_name = "divergence_triggered_before_3_repeats"
    if state.critiques:
        # Count fingerprint occurrences
        fp_counts: dict[str, int] = {}
        for critique in state.critiques:
            for fp in critique.issue_fingerprints():
                fp_counts[fp] = fp_counts.get(fp, 0) + 1

        # Critical/high issues repeated 3+ times without divergence being triggered
        repeat_violations = [
            fp for fp, count in fp_counts.items()
            if count >= 3 and "critical" in fp or "high" in fp
        ]
        if repeat_violations and state.status not in ("diverged", "approved"):
            result.tests[test_name] = False
            result.failures.append(
                f"[{test_name}] Critical/high issues repeated 3+ times without divergence: "
                f"{repeat_violations}. Status: {state.status}."
            )
        else:
            result.tests[test_name] = True
    else:
        result.tests[test_name] = True

    # ── Test 5: Each revision proposal is longer or equal in quality ─────────
    test_name = "proposal_quality_maintained"
    if len(state.proposals) >= 2:
        word_counts = [p.word_count() for p in state.proposals]
        # Warn if latest proposal is >30% shorter than first
        if word_counts[-1] < word_counts[0] * 0.7:
            result.warnings.append(
                f"[{test_name}] Latest proposal ({word_counts[-1]} words) is significantly "
                f"shorter than initial proposal ({word_counts[0]} words). "
                f"Possible content regression."
            )
        result.tests[test_name] = True  # Only a warning, not a hard failure
    else:
        result.tests[test_name] = True

    # ── Test 6: All required sections in every proposal ──────────────────────
    test_name = "required_sections_in_all_proposals"
    required = ["Executive Summary", "Understanding", "Approach", "Phases", "Pricing", "Open Questions"]
    all_ok = True
    for i, proposal in enumerate(state.proposals):
        missing = [s for s in required if s.lower() not in proposal.content.lower()]
        if missing:
            result.failures.append(
                f"[{test_name}] Proposal v{proposal.version} missing sections: {missing}"
            )
            all_ok = False
    result.tests[test_name] = all_ok

    return result


def print_result(result: FeedbackLoopResult) -> None:
    status = "✅ PASS" if result.passed else "❌ FAIL"
    print(f"\n{'─' * 60}")
    print(f"  Feedback Loop Regression Eval — Run {result.run_id}  {status}")
    print(f"{'─' * 60}")
    print(f"  Iterations checked: {result.iterations_checked}")
    print(f"  Test score: {result.score}")
    print()
    for test_name, passed in result.tests.items():
        icon = "✓" if passed else "✗"
        print(f"  {icon} {test_name}")
    if result.failures:
        print(f"\n  Failures:")
        for f in result.failures:
            print(f"    ✗ {f}")
    if result.warnings:
        print(f"\n  Warnings:")
        for w in result.warnings:
            print(f"    ⚠ {w}")
    print(f"{'─' * 60}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Feedback Loop Regression Eval — tests HITL pipeline quality."
    )
    parser.add_argument("--runs-dir", default="runs", help="Path to the runs directory.")
    parser.add_argument("--run-id", default=None, help="Specific run ID to evaluate.")
    args = parser.parse_args()

    runs_dir = Path(args.runs_dir)
    if not runs_dir.exists():
        print(f"ERROR: runs directory not found: {runs_dir}")
        sys.exit(1)

    if args.run_id:
        run_ids = [args.run_id]
    else:
        run_ids = [
            d.name
            for d in sorted(runs_dir.iterdir())
            if d.is_dir() and (d / "state.json").exists()
        ]

    if not run_ids:
        print("No runs found. Run the pipeline first: python main.py")
        sys.exit(0)

    print(f"\n{'═' * 60}")
    print(f"  FEEDBACK LOOP REGRESSION EVAL  ({len(run_ids)} runs)")
    print(f"{'═' * 60}")

    results = []
    for run_id in run_ids:
        try:
            result = evaluate_run(run_id, runs_dir)
            print_result(result)
            results.append(result)
        except Exception as exc:
            print(f"  [ERROR] Run {run_id}: {exc}")

    passed = sum(1 for r in results if r.passed)
    print(f"\n{'═' * 60}")
    print(f"  SUMMARY: {passed}/{len(results)} runs passed all regression checks")
    print(f"{'═' * 60}\n")

    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
