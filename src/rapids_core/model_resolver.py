"""Model resolution: maps (tier, phase, capability) to a model configuration."""

from __future__ import annotations

from rapids_core.models import ModelConfig

# Default model assignments by tier and phase
# Format: (tier, phase) -> (model, effort)
_DEFAULTS: dict[tuple[int, str], tuple[str, str]] = {
    # Tier 1: fast and cheap
    (1, "implement"): ("haiku", "low"),
    # Tier 2
    (2, "plan"): ("sonnet", "medium"),
    (2, "implement"): ("sonnet", "medium"),
    # Tier 3
    (3, "analysis"): ("opus", "high"),
    (3, "plan"): ("sonnet", "medium"),
    (3, "implement"): ("sonnet", "medium"),
    (3, "deploy"): ("sonnet", "medium"),
    # Tier 4
    (4, "research"): ("opus", "high"),
    (4, "analysis"): ("opus", "high"),
    (4, "plan"): ("sonnet", "high"),
    (4, "implement"): ("sonnet", "medium"),
    (4, "deploy"): ("sonnet", "medium"),
    # Tier 5
    (5, "research"): ("opus", "high"),
    (5, "analysis"): ("opus", "high"),
    (5, "plan"): ("opus", "high"),
    (5, "implement"): ("sonnet", "high"),
    (5, "deploy"): ("sonnet", "high"),
    (5, "sustain"): ("sonnet", "medium"),
}

# Model hierarchy for minimum enforcement
_MODEL_RANK = {"haiku": 0, "sonnet": 1, "opus": 2}
_EFFORT_RANK = {"low": 0, "medium": 1, "high": 2}


def resolve_model(
    tier: int,
    phase: str,
    capability: str | None = None,
    user_override: dict | None = None,
    plugin_minimum: dict | None = None,
) -> ModelConfig:
    """Resolve the model configuration for a given context.

    Precedence: user_override > plugin_minimum > tier/phase default.

    Args:
        tier: Scope tier (1-5).
        phase: Current phase name.
        capability: Optional capability ID (for future per-capability tuning).
        user_override: Optional dict with "model" and/or "effort" keys.
        plugin_minimum: Optional dict with "model" and/or "effort" minimum requirements.

    Returns:
        ModelConfig with resolved model, effort, and max_turns.
    """
    # Start with defaults
    key = (tier, phase)
    if key in _DEFAULTS:
        default_model, default_effort = _DEFAULTS[key]
    else:
        # Fallback for unknown combinations
        default_model = "sonnet"
        default_effort = "medium"

    model = default_model
    effort = default_effort

    # Apply plugin minimum (raise floor but don't lower ceiling)
    if plugin_minimum:
        min_model = plugin_minimum.get("model")
        if min_model and _MODEL_RANK.get(min_model, 0) > _MODEL_RANK.get(model, 0):
            model = min_model

        min_effort = plugin_minimum.get("effort")
        if min_effort and _EFFORT_RANK.get(min_effort, 0) > _EFFORT_RANK.get(effort, 0):
            effort = min_effort

    # Apply user override (takes absolute precedence)
    if user_override:
        if "model" in user_override:
            model = user_override["model"]
        if "effort" in user_override:
            effort = user_override["effort"]

    # Determine max_turns based on tier and effort
    turns_map = {"low": 30, "medium": 50, "high": 100}
    max_turns = turns_map.get(effort, 50)
    if tier >= 4:
        max_turns = max(max_turns, 100)
    if tier >= 5:
        max_turns = max(max_turns, 200)

    return ModelConfig(model=model, effort=effort, max_turns=max_turns)
