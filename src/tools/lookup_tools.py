"""Tool definitions for Claude tool-use API.

These tools are invoked via Claude's native tool-use mechanism — NOT via
prompt injection. Results come from static mock data in data/engagement_history.json.

Three tools:
  1. crm_lookup          — company relationship history and contacts
  2. pricing_benchmark   — industry pricing reference data
  3. engagement_history  — similar past engagements and case studies
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ── Static data store ────────────────────────────────────────────────────────

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
_ENGAGEMENT_DB: dict | None = None


def _load_db() -> dict:
    global _ENGAGEMENT_DB
    if _ENGAGEMENT_DB is None:
        db_path = _DATA_DIR / "engagement_history.json"
        if db_path.exists():
            with open(db_path, encoding="utf-8") as f:
                _ENGAGEMENT_DB = json.load(f)
        else:
            _ENGAGEMENT_DB = {}
    return _ENGAGEMENT_DB


# ── Tool implementations ──────────────────────────────────────────────────────

def crm_lookup(company_name: str, contact_name: str | None = None) -> dict[str, Any]:
    """Look up a company in the CRM.

    Returns relationship history, key contacts, and any flagged risks.
    """
    db = _load_db()
    companies = db.get("crm", {})

    # Fuzzy match on company name
    key = None
    for name in companies:
        if name.lower() in company_name.lower() or company_name.lower() in name.lower():
            key = name
            break

    if key:
        result = companies[key].copy()
        if contact_name:
            # Filter to specific contact if requested
            contacts = result.get("contacts", [])
            matched = [c for c in contacts if contact_name.lower() in c.get("name", "").lower()]
            if matched:
                result["contacts"] = matched
    else:
        result = {
            "found": False,
            "message": f"No CRM record found for '{company_name}'.",
            "similar_companies": list(companies.keys())[:3],
        }
        return result

    result["found"] = True
    return result


def pricing_benchmark(industry: str, project_scope: str, duration_months: int) -> dict[str, Any]:
    """Return pricing benchmark data for a given industry and project scope.

    Args:
        industry: e.g. "freight brokerage", "logistics", "SaaS"
        project_scope: e.g. "workflow automation", "system integration", "platform rebuild"
        duration_months: Engagement duration in months

    Returns:
        Benchmark ranges with percentiles and notes.
    """
    db = _load_db()
    benchmarks = db.get("pricing_benchmarks", {})

    # Try to match industry
    matched_industry = None
    for ind in benchmarks:
        if ind.lower() in industry.lower() or industry.lower() in ind.lower():
            matched_industry = ind
            break

    if not matched_industry:
        # Return general benchmark
        return {
            "industry": industry,
            "scope": project_scope,
            "duration_months": duration_months,
            "note": "No exact industry match — using general mid-market benchmarks",
            "benchmark": {
                "p25_usd": 150_000,
                "p50_usd": 275_000,
                "p75_usd": 450_000,
                "p90_usd": 750_000,
            },
            "typical_structure": "Fixed-fee with milestone payments (60% / 20% / 20%)",
            "day_rate_range": "$2,500–$3,500/day (senior consultant)",
        }

    scope_data = benchmarks[matched_industry]
    # Adjust for duration
    base = scope_data.get("base_engagement", {})
    duration_multiplier = duration_months / 6.0  # Normalized to 6-month baseline

    return {
        "industry": matched_industry,
        "scope": project_scope,
        "duration_months": duration_months,
        "benchmark": {
            "p25_usd": int(base.get("p25", 200_000) * duration_multiplier),
            "p50_usd": int(base.get("p50", 350_000) * duration_multiplier),
            "p75_usd": int(base.get("p75", 550_000) * duration_multiplier),
            "p90_usd": int(base.get("p90", 900_000) * duration_multiplier),
        },
        "typical_structure": scope_data.get(
            "typical_structure",
            "Fixed-fee with milestone payments",
        ),
        "notes": scope_data.get("notes", []),
        "day_rate_range": scope_data.get("day_rate_range", "$2,500–$3,500/day"),
        "comparable_clients": scope_data.get("comparable_clients", []),
    }


def engagement_history(
    industry: str,
    problem_type: str,
    max_results: int = 3,
) -> dict[str, Any]:
    """Retrieve similar past engagement case studies.

    Args:
        industry: Target industry to match
        problem_type: Problem category (e.g. "workflow automation", "data integration")
        max_results: Maximum number of case studies to return

    Returns:
        List of matching engagements with outcomes.
    """
    db = _load_db()
    engagements = db.get("past_engagements", [])

    # Score each engagement by relevance
    scored = []
    for eng in engagements:
        score = 0
        if industry.lower() in eng.get("industry", "").lower():
            score += 3
        for pt in eng.get("problem_types", []):
            if problem_type.lower() in pt.lower() or pt.lower() in problem_type.lower():
                score += 2
        if score > 0:
            scored.append((score, eng))

    scored.sort(key=lambda x: -x[0])
    results = [eng for _, eng in scored[:max_results]]

    if not results:
        return {
            "found": False,
            "message": f"No matching engagements for industry='{industry}', "
            f"problem_type='{problem_type}'.",
            "suggestion": "Consider the Cascade Freight engagement (freight brokerage, 2024).",
        }

    return {
        "found": True,
        "count": len(results),
        "engagements": results,
        "summary": f"Found {len(results)} relevant past engagement(s) matching "
        f"'{industry}' / '{problem_type}'.",
    }


# ── Tool dispatch ─────────────────────────────────────────────────────────────

_TOOL_REGISTRY: dict[str, Any] = {
    "crm_lookup": crm_lookup,
    "pricing_benchmark": pricing_benchmark,
    "engagement_history": engagement_history,
}


def dispatch_tool_call(tool_name: str, tool_input: dict[str, Any]) -> Any:
    """Dispatch a Claude tool call to the correct implementation.

    Returns the result (will be serialized to JSON for Claude).
    """
    if tool_name not in _TOOL_REGISTRY:
        return {"error": f"Unknown tool: '{tool_name}'. Available: {list(_TOOL_REGISTRY.keys())}"}
    try:
        return _TOOL_REGISTRY[tool_name](**tool_input)
    except TypeError as e:
        return {"error": f"Invalid arguments for tool '{tool_name}': {e}"}
    except Exception as e:
        return {"error": f"Tool '{tool_name}' failed: {type(e).__name__}: {e}"}


# ── Claude tool schema definitions ───────────────────────────────────────────

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "crm_lookup",
        "description": (
            "Look up a company or contact in the CRM database. "
            "Returns relationship history, key contacts, previous interactions, "
            "and any risk flags. Use this to understand existing client relationships "
            "before generating a proposal."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "string",
                    "description": "The company name to look up (e.g. 'Northwind Logistics').",
                },
                "contact_name": {
                    "type": "string",
                    "description": "Optional: specific contact to filter results by.",
                },
            },
            "required": ["company_name"],
        },
    },
    {
        "name": "pricing_benchmark",
        "description": (
            "Retrieve pricing benchmark data for a given industry, project scope, "
            "and engagement duration. Returns p25/p50/p75/p90 fee ranges, typical "
            "contract structures, and comparable client examples. Use this to inform "
            "the Pricing Approach section of a proposal."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "industry": {
                    "type": "string",
                    "description": "Client industry (e.g. 'freight brokerage', 'logistics').",
                },
                "project_scope": {
                    "type": "string",
                    "description": "Type of project (e.g. 'workflow automation', 'system integration').",
                },
                "duration_months": {
                    "type": "integer",
                    "description": "Expected engagement duration in months.",
                },
            },
            "required": ["industry", "project_scope", "duration_months"],
        },
    },
    {
        "name": "engagement_history",
        "description": (
            "Search past engagement case studies by industry and problem type. "
            "Returns relevant previous work with outcomes, timelines, and lessons learned. "
            "Use this to reference comparable engagements and strengthen proposal credibility."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "industry": {
                    "type": "string",
                    "description": "Industry to search (e.g. 'freight brokerage').",
                },
                "problem_type": {
                    "type": "string",
                    "description": "Problem type to match (e.g. 'workflow automation', 'data integration').",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 3).",
                    "default": 3,
                },
            },
            "required": ["industry", "problem_type"],
        },
    },
]
