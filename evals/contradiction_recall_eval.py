"""Eval: Contradiction Recall

Tests that the Debrief Agent correctly:
  1. Identifies all contradictions present in the source transcripts
  2. Marks them with confidence="contradicted"
  3. Includes a non-empty contradiction_note for each

Known ground-truth contradictions in Northwind Logistics transcripts:
  - Budget: Sarah said $250k–$400k (Transcript A), Rita said "$300k cap" (Transcript B)
  - Timeline: Sarah committed to Q3, Marcus said Q3 was never agreed and Q4 is realistic
  - Driver app scope: Sarah says defer, Marcus says it overlaps with ELD (partially contradicted)
  - ELD in-scope: Sarah says not in scope, Marcus says it must be coordinated

Usage:
  python -m evals.contradiction_recall_eval [--runs-dir runs/] [--run-id <id>]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.state import RunState
from src.schemas.matrix import ConfidenceLevel, ClientMatrix

# ── Ground-truth contradictions ───────────────────────────────────────────────

KNOWN_CONTRADICTIONS = [
    {
        "id": "budget_disagreement",
        "description": "Budget cap: Sarah said $250k–$400k range; Rita said hard cap of $300k",
        "keywords": ["budget", "300", "250", "400"],
        "category": "business",
    },
    {
        "id": "timeline_q3_vs_q4",
        "description": "Timeline: Sarah/Rita committed Q3; Marcus said Q3 was never agreed and Q4 is realistic",
        "keywords": ["q3", "q4", "timeline", "deadline", "september"],
        "category": "strategic",
    },
    {
        "id": "platform_rebuild_vs_incremental",
        "description": "CTO wants full Routemaster rebuild; VP Ops wants incremental fixes",
        "keywords": ["rebuild", "routemaster", "platform", "incremental", "band-aid"],
        "category": "technical",
    },
    {
        "id": "eld_scope",
        "description": "ELD compliance: Sarah says not in scope; Marcus says driver app touches ELD",
        "keywords": ["eld", "compliance", "driver app", "scope"],
        "category": "operational",
    },
]


@dataclass
class ContradictionEvalResult:
    run_id: str
    total_matrix_items: int
    contradicted_items_found: int
    contradiction_notes_present: int
    contradiction_notes_missing: list[str]
    known_contradictions_recalled: list[str]
    known_contradictions_missed: list[str]
    precision: float   # Of items marked contradicted, how many had proper notes
    recall: float      # Of known contradictions, how many were captured
    passed: bool


def evaluate_run(run_id: str, runs_dir: Path) -> ContradictionEvalResult:
    """Evaluate a single run's contradiction recall."""
    state = RunState.load(run_id, runs_dir)

    if state.matrix is None:
        print(f"  [SKIP] Run {run_id}: no matrix found (debrief may not have completed).")
        return ContradictionEvalResult(
            run_id=run_id,
            total_matrix_items=0,
            contradicted_items_found=0,
            contradiction_notes_present=0,
            contradiction_notes_missing=[],
            known_contradictions_recalled=[],
            known_contradictions_missed=[name["id"] for name in KNOWN_CONTRADICTIONS],
            precision=0.0,
            recall=0.0,
            passed=False,
        )

    matrix = state.matrix

    # Count all matrix items
    total_items = 0
    contradicted_items = []
    notes_missing = []

    for dim_name in ("business", "technical", "operational", "strategic"):
        dim = getattr(matrix, dim_name)
        for aspect in ("pain_points", "desired_state", "success_criteria", "risks_unknowns"):
            item = getattr(dim, aspect)
            total_items += 1
            if item.confidence == ConfidenceLevel.CONTRADICTED:
                label = f"{dim_name}/{aspect}"
                contradicted_items.append((label, item))
                if not item.contradiction_note or len(item.contradiction_note.strip()) < 10:
                    notes_missing.append(label)

    notes_present = len(contradicted_items) - len(notes_missing)

    # Check recall of known contradictions
    all_matrix_text = json.dumps(matrix.model_dump()).lower()
    recalled = []
    missed = []

    for known in KNOWN_CONTRADICTIONS:
        keyword_hits = sum(
            1 for kw in known["keywords"] if kw.lower() in all_matrix_text
        )
        # A known contradiction is "recalled" if:
        #   (a) keywords appear in the matrix AND
        #   (b) at least one contradicted item exists in the relevant dimension
        dim_has_contradiction = any(
            dim_name == known["category"] and item.confidence == ConfidenceLevel.CONTRADICTED
            for dim_name in (known["category"],)
            for dim in [getattr(matrix, known["category"])]
            for aspect in ("pain_points", "desired_state", "success_criteria", "risks_unknowns")
            for item in [getattr(dim, aspect)]
        )

        if keyword_hits >= 2 and dim_has_contradiction:
            recalled.append(known["id"])
        else:
            missed.append(known["id"])

    precision = (
        notes_present / len(contradicted_items) if contradicted_items else 1.0
    )
    recall = len(recalled) / len(KNOWN_CONTRADICTIONS)
    passed = precision >= 0.8 and recall >= 0.5

    return ContradictionEvalResult(
        run_id=run_id,
        total_matrix_items=total_items,
        contradicted_items_found=len(contradicted_items),
        contradiction_notes_present=notes_present,
        contradiction_notes_missing=notes_missing,
        known_contradictions_recalled=recalled,
        known_contradictions_missed=missed,
        precision=precision,
        recall=recall,
        passed=passed,
    )


def print_result(result: ContradictionEvalResult) -> None:
    status = "✅ PASS" if result.passed else "❌ FAIL"
    print(f"\n{'─' * 60}")
    print(f"  Contradiction Recall Eval — Run {result.run_id}  {status}")
    print(f"{'─' * 60}")
    print(f"  Matrix items total:         {result.total_matrix_items}")
    print(f"  Contradicted items found:   {result.contradicted_items_found}")
    print(f"  Notes present:              {result.contradiction_notes_present}")
    print(f"  Notes missing:              {len(result.contradiction_notes_missing)}")
    if result.contradiction_notes_missing:
        for loc in result.contradiction_notes_missing:
            print(f"    ✗ Missing note at: {loc}")
    print(f"\n  Known contradictions recalled ({len(result.known_contradictions_recalled)}/{len(KNOWN_CONTRADICTIONS)}):")
    for cid in result.known_contradictions_recalled:
        print(f"    ✓ {cid}")
    if result.known_contradictions_missed:
        print(f"\n  Missed contradictions:")
        for cid in result.known_contradictions_missed:
            print(f"    ✗ {cid}")
    print(f"\n  Precision:  {result.precision:.1%}")
    print(f"  Recall:     {result.recall:.1%}")
    print(f"{'─' * 60}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Contradiction Recall Eval — tests Debrief Agent accuracy."
    )
    parser.add_argument(
        "--runs-dir",
        default="runs",
        help="Path to the runs directory (default: runs/)",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Specific run ID to evaluate (default: all runs)",
    )
    args = parser.parse_args()

    runs_dir = Path(args.runs_dir)
    if not runs_dir.exists():
        print(f"ERROR: runs directory not found: {runs_dir}")
        sys.exit(1)

    # Collect run IDs to evaluate
    if args.run_id:
        run_ids = [args.run_id]
    else:
        run_ids = [
            d.name
            for d in sorted(runs_dir.iterdir())
            if d.is_dir() and (d / "state.json").exists()
        ]

    if not run_ids:
        print("No runs found to evaluate. Run the pipeline first with: python main.py")
        sys.exit(0)

    print(f"\n{'═' * 60}")
    print(f"  CONTRADICTION RECALL EVAL  ({len(run_ids)} runs)")
    print(f"{'═' * 60}")

    results = []
    for run_id in run_ids:
        try:
            result = evaluate_run(run_id, runs_dir)
            print_result(result)
            results.append(result)
        except Exception as exc:
            print(f"  [ERROR] Run {run_id}: {exc}")

    # Summary
    passed = sum(1 for r in results if r.passed)
    avg_recall = sum(r.recall for r in results) / len(results) if results else 0
    avg_precision = sum(r.precision for r in results) / len(results) if results else 0

    print(f"\n{'═' * 60}")
    print(f"  SUMMARY: {passed}/{len(results)} runs passed")
    print(f"  Avg Precision: {avg_precision:.1%}")
    print(f"  Avg Recall:    {avg_recall:.1%}")
    print(f"{'═' * 60}\n")

    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
