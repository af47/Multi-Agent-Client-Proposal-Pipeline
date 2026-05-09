#!/usr/bin/env python3
"""Client Proposal Pipeline — CLI Entrypoint.

Usage:
  python main.py                            # Run both transcripts interactively
  python main.py --transcript a             # Transcript A only
  python main.py --transcript b             # Transcript B only
  python main.py --transcript both          # Both transcripts (default)
  python main.py --non-interactive          # Auto-approve (no stdin required)
  python main.py --resume <run_id>          # Resume a saved run
  python main.py --eval                     # Run both eval scripts on saved runs
  python main.py --list-runs               # List all saved runs
  python main.py --max-iterations 3         # Set iteration limit
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env before importing anything else
load_dotenv()

from src.core.claude_client import ClaudeClient, PipelineError
from src.core.orchestrator import PipelineOrchestrator
from src.core.state import RunState
from src.utils.loader import InputLoader

BASE_DIR = Path(__file__).parent
INPUTS_DIR = BASE_DIR / "inputs"
RUNS_DIR = BASE_DIR / "runs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Client Proposal Pipeline — Multi-Agent AI System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--transcript",
        choices=["a", "b", "both"],
        default="both",
        help="Which transcript(s) to process (default: both)",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Auto-approve proposals without waiting for human input (useful for CI/eval)",
    )
    parser.add_argument(
        "--resume",
        metavar="RUN_ID",
        default=None,
        help="Resume a previously saved run by its run ID",
    )
    parser.add_argument(
        "--eval",
        action="store_true",
        help="Run both eval scripts against all saved runs",
    )
    parser.add_argument(
        "--list-runs",
        action="store_true",
        help="List all saved runs with their summaries",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=int(os.getenv("MAX_ITERATIONS", "5")),
        help="Maximum number of proposal revision iterations (default: 5)",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022"),
        help="Claude model to use (default: claude-3-5-sonnet-20241022)",
    )
    return parser.parse_args()


def run_evals() -> None:
    """Run both eval scripts."""
    print("\n" + "═" * 60)
    print("  RUNNING EVAL SUITE")
    print("═" * 60)

    evals = [
        "evals/contradiction_recall_eval.py",
        "evals/feedback_loop_regression_eval.py",
    ]

    all_passed = True
    for eval_path in evals:
        print(f"\n▶ Running: {eval_path}")
        result = subprocess.run(
            [sys.executable, eval_path, "--runs-dir", str(RUNS_DIR)],
            cwd=BASE_DIR,
        )
        if result.returncode != 0:
            all_passed = False

    print("\n" + "═" * 60)
    print(f"  EVAL SUITE: {'✅ ALL PASSED' if all_passed else '❌ SOME FAILED'}")
    print("═" * 60)
    sys.exit(0 if all_passed else 1)


def list_runs() -> None:
    """Print a table of all saved runs."""
    runs = RunState.list_runs(RUNS_DIR)
    if not runs:
        print("No saved runs found. Run the pipeline first: python main.py")
        return

    print(f"\n{'─' * 80}")
    print(f"  {'RUN ID':<10} {'LABEL':<25} {'STATUS':<15} {'ITER':<6} {'COST':>8}  {'CREATED'}")
    print(f"{'─' * 80}")
    for r in runs:
        print(
            f"  {r['run_id']:<10} "
            f"{r.get('run_label', '')[:24]:<25} "
            f"{r.get('status', ''):<15} "
            f"{r.get('iteration', 0):<6} "
            f"${r.get('total_cost_usd', 0):.4f}  "
            f"{r.get('created_at', '')[:19]}"
        )
    print(f"{'─' * 80}\n")


def run_pipeline(
    transcript_filter: str | None,
    non_interactive: bool,
    max_iterations: int,
    model: str,
    run_label: str,
) -> RunState:
    """Run the pipeline for a given transcript filter."""
    # Validate API key early
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "\n❌ ERROR: ANTHROPIC_API_KEY is not set.\n"
            "   Copy .env.template to .env and add your API key:\n"
            "   cp .env.template .env\n"
        )
        sys.exit(1)

    # Load inputs
    loader = InputLoader(INPUTS_DIR)
    try:
        inputs = loader.load(
            transcript_filter=transcript_filter,
            run_label=run_label,
        )
    except FileNotFoundError as e:
        print(f"❌ ERROR: {e}")
        sys.exit(1)

    print(f"\n{'═' * 60}")
    print(f"  CLIENT PROPOSAL PIPELINE")
    print(f"{'═' * 60}")
    print(f"  Inputs:   {inputs.summary()}")
    print(f"  Model:    {model}")
    print(f"  Max iter: {max_iterations}")
    print(f"  Mode:     {'non-interactive' if non_interactive else 'interactive'}")
    print(f"{'═' * 60}\n")

    # Initialize client and orchestrator
    client = ClaudeClient(api_key=api_key, model=model)
    orchestrator = PipelineOrchestrator(
        client=client,
        runs_dir=RUNS_DIR,
        max_iterations=max_iterations,
        non_interactive=non_interactive,
    )

    # Run pipeline
    state = orchestrator.run(inputs)
    return state


def resume_pipeline(run_id: str, non_interactive: bool, model: str) -> RunState:
    """Resume a previously saved pipeline run."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ERROR: ANTHROPIC_API_KEY is not set.")
        sys.exit(1)

    # Load minimal inputs (needed for feedback context only)
    loader = InputLoader(INPUTS_DIR)
    inputs = loader.load()

    client = ClaudeClient(api_key=api_key, model=model)
    orchestrator = PipelineOrchestrator(
        client=client,
        runs_dir=RUNS_DIR,
        non_interactive=non_interactive,
    )

    state = orchestrator.resume(run_id=run_id, inputs=inputs)
    return state


def print_final_summary(state: RunState) -> None:
    """Print a clean final summary after pipeline completes."""
    proposal = state.current_proposal()
    critique = state.current_critique()

    print(f"\n{'═' * 60}")
    print(f"  PIPELINE COMPLETE")
    print(f"{'═' * 60}")
    print(f"  Run ID:          {state.run_id}")
    print(f"  Status:          {state.status.upper()}")
    print(f"  Iterations:      {state.iteration}")
    print(f"  Total cost:      ${state.total_cost_usd:.4f}")
    print(f"  Total tokens:    {state.total_tokens:,}")
    if proposal:
        print(f"  Final proposal:  v{proposal.version} ({proposal.word_count()} words)")
        print(f"  Saved to:        runs/{state.run_id}/latest_proposal.md")
    if critique:
        print(f"  Final score:     {critique.overall_score}/10")
        print(f"  Recommendation:  {critique.recommendation.value}")
    print(f"  Full trace:      runs/{state.run_id}/traces.jsonl")
    print(f"{'═' * 60}\n")


def main() -> None:
    args = parse_args()
    RUNS_DIR.mkdir(exist_ok=True)

    # ── Subcommands ──────────────────────────────────────────────────────────

    if args.eval:
        run_evals()
        return

    if args.list_runs:
        list_runs()
        return

    if args.resume:
        try:
            state = resume_pipeline(
                run_id=args.resume,
                non_interactive=args.non_interactive,
                model=args.model,
            )
            print_final_summary(state)
        except PipelineError as e:
            print(f"❌ Pipeline error: {e}")
            sys.exit(1)
        return

    # ── Main pipeline run ────────────────────────────────────────────────────

    transcript_filter = None if args.transcript == "both" else args.transcript

    # Run transcript A
    if args.transcript in ("a", "both"):
        try:
            state_a = run_pipeline(
                transcript_filter="a",
                non_interactive=args.non_interactive,
                max_iterations=args.max_iterations,
                model=args.model,
                run_label="intake+transcript_a",
            )
            print_final_summary(state_a)
        except PipelineError as e:
            print(f"❌ Pipeline error (transcript A): {e}")
            sys.exit(1)

    # Run transcript B
    if args.transcript in ("b", "both"):
        try:
            state_b = run_pipeline(
                transcript_filter="b",
                non_interactive=args.non_interactive,
                max_iterations=args.max_iterations,
                model=args.model,
                run_label="intake+transcript_b",
            )
            print_final_summary(state_b)
        except PipelineError as e:
            print(f"❌ Pipeline error (transcript B): {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
