"""Model Router — smart model selection based on task type.

Routes each agent call to the most cost-efficient Claude model:

  SONNET (claude-3-5-sonnet-20241022)  ← heavy reasoning, generation, analysis
    • DebriefAgent      — contradiction detection, matrix extraction from long docs
    • ProposalAgent     — long-form constrained generation
    • ReviewAgent.critique — multi-criteria scoring, nuanced quality judgment

  HAIKU (claude-3-5-haiku-20241022)   ← classification, structuring, simple transforms
    • ReviewAgent.translate_feedback — classify + structure human feedback
    • Schema validation retries       — just fix bad JSON format

Pricing (per million tokens):
  Sonnet:  $3.00 input  / $15.00 output
  Haiku:   $0.80 input  /  $4.00 output

Expected savings: ~35–45% cost reduction vs. using Sonnet for all calls,
primarily driven by Haiku handling feedback translation and validation retries.
"""

from __future__ import annotations

import os
from enum import Enum
from typing import NamedTuple


class ModelTier(str, Enum):
    """Semantic tier — decoupled from specific model strings."""
    SONNET = "sonnet"   # Heavy reasoning / generation
    HAIKU = "haiku"     # Classification / structuring / simple transforms


class ModelPricing(NamedTuple):
    """Per-million-token pricing for a model."""
    input_usd_per_m: float
    output_usd_per_m: float


# ── Model identifiers ─────────────────────────────────────────────────────────

_DEFAULT_SONNET = "claude-3-5-sonnet-20241022"
_DEFAULT_HAIKU = "claude-3-5-haiku-20241022"

# Pricing constants
_PRICING: dict[ModelTier, ModelPricing] = {
    ModelTier.SONNET: ModelPricing(input_usd_per_m=3.00, output_usd_per_m=15.00),
    ModelTier.HAIKU:  ModelPricing(input_usd_per_m=0.80, output_usd_per_m=4.00),
}


class ModelRouter:
    """Selects the appropriate Claude model for each task type.

    Model strings are resolved from environment variables so they can be
    overridden without code changes:
        SONNET_MODEL=claude-3-5-sonnet-20241022
        HAIKU_MODEL=claude-3-5-haiku-20241022
    """

    def __init__(self) -> None:
        self._models: dict[ModelTier, str] = {
            ModelTier.SONNET: os.getenv("SONNET_MODEL", _DEFAULT_SONNET),
            ModelTier.HAIKU:  os.getenv("HAIKU_MODEL", _DEFAULT_HAIKU),
        }

    def get_model(self, tier: ModelTier) -> str:
        """Return the model identifier string for a given tier."""
        return self._models[tier]

    def estimate_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        """Estimate USD cost for an API call given the actual model used."""
        tier = self._resolve_tier(model)
        pricing = _PRICING[tier]
        return (
            (prompt_tokens / 1_000_000) * pricing.input_usd_per_m
            + (completion_tokens / 1_000_000) * pricing.output_usd_per_m
        )

    def _resolve_tier(self, model: str) -> ModelTier:
        """Map a model string back to its tier for pricing purposes."""
        haiku_model = self._models[ModelTier.HAIKU]
        if "haiku" in model.lower() or model == haiku_model:
            return ModelTier.HAIKU
        return ModelTier.SONNET  # Default to Sonnet pricing for unknown models

    def describe(self) -> str:
        """Human-readable description of current routing config."""
        s = self._models[ModelTier.SONNET]
        h = self._models[ModelTier.HAIKU]
        sp = _PRICING[ModelTier.SONNET]
        hp = _PRICING[ModelTier.HAIKU]
        return (
            f"ModelRouter:\n"
            f"  SONNET → {s}  (${sp.input_usd_per_m}/M in, ${sp.output_usd_per_m}/M out)\n"
            f"  HAIKU  → {h}  (${hp.input_usd_per_m}/M in, ${hp.output_usd_per_m}/M out)\n"
            f"\nTask routing:\n"
            f"  SONNET: DebriefAgent, ProposalAgent, ReviewAgent.critique\n"
            f"  HAIKU:  ReviewAgent.translate_feedback, schema validation retries"
        )


# ── Module-level singleton (lazy) ─────────────────────────────────────────────

_router: ModelRouter | None = None


def get_router() -> ModelRouter:
    """Return the shared ModelRouter singleton."""
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router


def estimate_cost_for_model(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Convenience function — estimate cost given a model string."""
    return get_router().estimate_cost(model, prompt_tokens, completion_tokens)
