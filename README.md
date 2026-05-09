# Client Proposal Pipeline

A production-grade multi-agent AI system that processes client intake forms and discovery call transcripts to generate structured proposals — with human-in-the-loop refinement, full observability, and run persistence.

Built with Python + Anthropic Claude SDK.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        main.py (CLI)                            │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│              PipelineOrchestrator (src/core/orchestrator.py)    │
│  Manages agent sequencing, HITL loop, divergence detection      │
└────────┬───────────────────────────────────────────┬────────────┘
         │                                           │
┌────────▼────────┐  ┌───────────────────┐  ┌───────▼────────────┐
│  DebriefAgent   │  │  ProposalAgent    │  │   ReviewAgent       │
│  4×4 Matrix     │  │  Markdown output  │  │   Critique +        │
│  + tool-use     │  │  + tool-use       │  │   Feedback translate│
└────────┬────────┘  └─────────┬─────────┘  └────────────────────┘
         │                     │
┌────────▼─────────────────────▼───────────────────────────────────┐
│              ClaudeClient (src/core/claude_client.py)            │
│  • Exponential backoff retry (1s→2s→4s)                         │
│  • Schema validation re-prompting (max 2 retries)               │
│  • Native tool-use multi-turn loop                              │
└──────────────────────────────────────────────────────────────────┘
```

### Agent Flow

```
1. DebriefAgent  →  ClientMatrix (4×4, validated Pydantic)
                    Uses: crm_lookup + engagement_history tools
                    
2. ProposalAgent →  ProposalOutput (Markdown, validated)
                    Uses: pricing_benchmark tool
                    
3. ReviewAgent   →  CritiqueOutput (score, issues, recommendation)
                    →  TranslatedFeedback (structured instructions)
                    
4. Human         →  Raw feedback (CLI)
                    Translated by ReviewAgent before passing to ProposalAgent
                    
Repeats until: approved | max iterations | divergence detected
```

---

## Setup

### 1. Clone and enter the project
```bash
cd Multi-Agent-Client-Proposal-Pipeline
```

### 2. Create a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate       # macOS/Linux
# .venv\Scripts\activate        # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure your API key
```bash
cp .env.template .env
# Edit .env and set ANTHROPIC_API_KEY=your_key_here
```

---

## Usage

### Run the full pipeline (both transcripts, interactive)
```bash
python main.py
```

### Run with a specific transcript
```bash
python main.py --transcript a    # Discovery call A only
python main.py --transcript b    # Discovery call B only (3 stakeholders)
```

### Non-interactive mode (auto-approve, useful for CI)
```bash
python main.py --non-interactive
```

### Resume a saved run
```bash
python main.py --list-runs                    # Show all saved runs
python main.py --resume <run_id>              # Resume from saved state
```

### Run evaluation scripts
```bash
python main.py --eval
# Or individually:
python -m evals.contradiction_recall_eval
python -m evals.feedback_loop_regression_eval
```

---

## Project Structure

```
├── main.py                          # CLI entrypoint
├── requirements.txt
├── .env.template
│
├── inputs/
│   ├── intake.md                    # Client intake form (Northwind Logistics)
│   ├── transcript_a.md              # Discovery call — Sarah Chen
│   └── transcript_b.md              # Discovery call — Sarah + Marcus + Rita
│
├── config/
│   └── master_prompt.md             # System architecture spec
│
├── data/
│   └── engagement_history.json      # Mock CRM/pricing/history data (tool backend)
│
├── runs/                            # Auto-created. One subdirectory per run.
│   └── <run_id>/
│       ├── state.json               # Full serialized RunState
│       ├── latest_proposal.md       # Final proposal (Markdown)
│       ├── traces.jsonl             # Per-agent observability traces
│       ├── pipeline.log             # Human-readable log
│       └── summary.json            # Quick-reference summary
│
├── src/
│   ├── agents/
│   │   ├── debrief_agent.py         # Extracts 4×4 Client Matrix
│   │   ├── proposal_agent.py        # Generates Markdown proposal
│   │   └── review_agent.py          # Critiques + translates feedback
│   │
│   ├── core/
│   │   ├── claude_client.py         # Anthropic SDK wrapper
│   │   ├── orchestrator.py          # Pipeline coordination
│   │   └── state.py                 # RunState + persistence
│   │
│   ├── schemas/
│   │   ├── matrix.py                # ClientMatrix Pydantic model
│   │   ├── proposal.py              # ProposalOutput model
│   │   └── review.py                # CritiqueOutput + TranslatedFeedback
│   │
│   ├── tools/
│   │   └── lookup_tools.py          # Tool definitions + dispatch
│   │
│   └── utils/
│       ├── loader.py                # Input file loader
│       └── logger.py                # Structured observability logger
│
└── evals/
    ├── contradiction_recall_eval.py  # Tests contradiction preservation
    └── feedback_loop_regression_eval.py  # Tests HITL loop quality
```

---

## Key Design Decisions

### Contradiction Preservation
The Debrief Agent **never resolves contradictions** — it marks them with `confidence: "contradicted"` and a `contradiction_note`. The Proposal Agent then routes these to the `Open Questions` section rather than stating them as facts.

Known contradictions in the Northwind Logistics transcripts:
- **Budget**: Sarah said $250k–$400k; Rita said $300k hard cap
- **Timeline**: Sarah/Rita committed Q3; Marcus said Q4 is realistic  
- **Platform**: Marcus wants full Routemaster rebuild; Sarah wants incremental
- **ELD scope**: Sarah says not in scope; Marcus says driver app touches ELD

### Tool-Use (Real Claude API)
Tools are invoked via Claude's native `tool_use` mechanism — NOT via prompt injection. The `ClaudeClient` runs a multi-turn loop: Claude requests a tool → we execute it → we inject the result → Claude continues.

Three tools: `crm_lookup`, `pricing_benchmark`, `engagement_history`.

### Failure Handling
| Failure | Strategy |
|---|---|
| `RateLimitError` | Exponential backoff: 1s → 2s → 4s (max 3 attempts) |
| `APIConnectionError` | Same backoff |
| Pydantic validation fails | Re-prompt Claude with error text, max 2 retries |
| Max retries exhausted | `PipelineError` raised, partial state saved |

### Divergence Detection
Pipeline stops early if:
- Any single issue fingerprint (e.g. `budget_ambiguity::high`) recurs in **3+ consecutive iterations**
- Critique score **degrades 2+ points** across 3 consecutive iterations

### Observability
Every agent call emits an `AgentTrace` with:
- Token usage + cost estimate (Claude 3.5 Sonnet rates: $3/M input, $15/M output)
- Latency in milliseconds
- Tool calls (name, input, output)
- Validation and API retry counts

Written to:
- `runs/<id>/traces.jsonl` — machine-readable per-call traces
- `runs/<id>/pipeline.log` — human-readable log

---

## Eval Scripts

### `contradiction_recall_eval`
Tests that the Debrief Agent correctly identifies and preserves contradictions.
- Checks all `contradicted` items have a `contradiction_note`
- Checks known contradictions (budget, timeline, platform, ELD) are recalled
- Reports precision + recall scores

### `feedback_loop_regression_eval`
Tests the HITL revision loop quality:
- Proposal version increments correctly
- `TranslatedFeedback` always contains structured instructions (never raw text passthrough)
- Critique scores don't degrade continuously
- All required sections present in every proposal
- Divergence triggers before an issue repeats 3×

---

## Cost Estimates

Approximate cost per full pipeline run (both transcripts, 2 iterations):

| Agent call | ~Tokens | ~Cost |
|---|---|---|
| DebriefAgent (+ tools) | ~12,000 | ~$0.09 |
| ProposalAgent × 2 (+ tools) | ~16,000 | ~$0.12 |
| ReviewAgent.critique × 2 | ~8,000 | ~$0.06 |
| ReviewAgent.translate × 1 | ~4,000 | ~$0.03 |
| **Total (both transcripts)** | **~80,000** | **~$0.60** |

Actual costs are logged per run in `runs/<id>/summary.json`.
