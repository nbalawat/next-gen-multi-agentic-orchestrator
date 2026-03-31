"""Scope classification: maps project signals to a scope tier (1-5) and phase list."""

from __future__ import annotations

from rapids_core.models import ScopeResult
from rapids_core.phase_router import route_phases


def classify_scope(signals: dict) -> ScopeResult:
    """Classify a work request into a scope tier based on input signals.

    Signals:
        description: str - Description of the work request
        files_impacted: int - Estimated number of files affected
        new_infrastructure: bool - Whether new infra is being created
        integrations: list[str] - External systems involved
        domain_complexity: str - "low", "moderate", or "high"

    Returns:
        ScopeResult with tier (1-5) and corresponding phases.
    """
    files = signals.get("files_impacted", 0)
    new_infra = signals.get("new_infrastructure", False)
    integrations = signals.get("integrations", [])
    complexity = signals.get("domain_complexity", "low")

    score = 0
    reasons = []

    # File impact scoring
    if files <= 2:
        score += 0
    elif files <= 8:
        score += 1
        reasons.append(f"{files} files impacted")
    elif files <= 25:
        score += 2
        reasons.append(f"{files} files impacted")
    elif files <= 60:
        score += 3
        reasons.append(f"{files} files impacted")
    else:
        score += 4
        reasons.append(f"{files}+ files impacted")

    # Infrastructure scoring
    if new_infra:
        score += 2
        reasons.append("new infrastructure required")

    # Integration scoring
    num_integrations = len(integrations)
    if num_integrations == 0:
        score += 0
    elif num_integrations <= 1:
        score += 1
        reasons.append(f"{num_integrations} integration")
    elif num_integrations <= 2:
        score += 2
        reasons.append(f"{num_integrations} integrations")
    else:
        score += 3
        reasons.append(f"{num_integrations} integrations")

    # Domain complexity scoring
    complexity_scores = {"low": 0, "moderate": 1, "high": 2}
    score += complexity_scores.get(complexity, 0)
    if complexity != "low":
        reasons.append(f"{complexity} domain complexity")

    # Map score to tier
    if score <= 1:
        tier = 1
    elif score <= 3:
        tier = 2
    elif score <= 6:
        tier = 3
    elif score <= 8:
        tier = 4
    else:
        tier = 5

    phases = route_phases(tier)
    reasoning = "; ".join(reasons) if reasons else "minimal scope"

    return ScopeResult(tier=tier, phases=phases, reasoning=reasoning)
