"""Wave computation: converts a dependency graph into execution waves via topological sort."""

from __future__ import annotations

from collections import defaultdict


class CircularDependencyError(Exception):
    """Raised when the dependency graph contains a cycle."""


def compute_waves(graph: dict) -> list[list[str]]:
    """Compute execution waves from a dependency graph.

    Features with no unmet dependencies go in the earliest possible wave.
    Features depending on earlier features go in later waves.

    Args:
        graph: Dict with "features" (list[str]) and "dependencies" (dict[str, list[str]]).

    Returns:
        List of waves, where each wave is a sorted list of feature IDs.

    Raises:
        CircularDependencyError: If the dependency graph contains a cycle.
    """
    features = graph.get("features", [])
    dependencies = graph.get("dependencies", {})

    if not features:
        return []

    # Validate all dependency targets exist
    all_features = set(features)
    for feature, deps in dependencies.items():
        for dep in deps:
            if dep not in all_features:
                raise ValueError(
                    f"Feature {feature} depends on {dep}, which is not in the feature list"
                )

    # Build in-degree map and reverse adjacency list
    in_degree: dict[str, int] = {f: 0 for f in features}
    dependents: dict[str, list[str]] = defaultdict(list)

    for feature, deps in dependencies.items():
        if feature in all_features:
            in_degree[feature] = len(deps)
            for dep in deps:
                dependents[dep].append(feature)

    # Kahn's algorithm adapted for wave grouping
    waves: list[list[str]] = []
    remaining = set(features)

    while remaining:
        # Find all features with no unmet dependencies
        ready = sorted(f for f in remaining if in_degree[f] == 0)

        if not ready:
            # All remaining features have unmet deps -> cycle
            raise CircularDependencyError(
                f"Circular dependency detected among: {sorted(remaining)}"
            )

        waves.append(ready)

        # Remove ready features and update in-degrees
        for feature in ready:
            remaining.remove(feature)
            for dependent in dependents[feature]:
                in_degree[dependent] -= 1

    return waves
