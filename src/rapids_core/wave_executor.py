"""Wave executor: decides between /batch and Agent Teams for wave execution."""

from __future__ import annotations


def choose_execution_method(
    wave_features: list[str],
    dependency_graph: dict,
    tier: int = 3,
    feature_plugins: dict[str, str] | None = None,
) -> str:
    """Decide whether to use /batch or Agent Teams for a wave.

    Use /batch when:
        - All features in the wave are independent (no cross-feature deps within the wave)
        - Each feature is scoped to a single plugin
        - Tier 2-3 (simpler, well-specified features)

    Use Agent Teams when:
        - Features need to coordinate (shared APIs, contracts)
        - Features span multiple plugins in the same wave
        - Tier 4-5 (complex, needs oversight)

    Args:
        wave_features: Feature IDs in this wave.
        dependency_graph: Full dependency graph dict.
        tier: Project scope tier (1-5).
        feature_plugins: Optional map of feature ID to plugin name.

    Returns:
        "batch" or "agent_teams".
    """
    if feature_plugins is None:
        feature_plugins = {}

    # Tier 4-5 always use Agent Teams for oversight
    if tier >= 4:
        return "agent_teams"

    # Single feature doesn't need coordination
    if len(wave_features) <= 1:
        return "batch"

    # Check if features share dependencies with each other within this wave
    dependencies = dependency_graph.get("dependencies", {})
    wave_set = set(wave_features)

    for feature in wave_features:
        deps = set(dependencies.get(feature, []))
        # If any dependency is within the same wave, they need coordination
        if deps & wave_set:
            return "agent_teams"

    # Check if features span multiple plugins
    plugins_in_wave = set()
    for feature in wave_features:
        plugin = feature_plugins.get(feature, "default")
        plugins_in_wave.add(plugin)

    if len(plugins_in_wave) > 1:
        return "agent_teams"

    # Independent, single-plugin, lower tier → batch
    return "batch"
