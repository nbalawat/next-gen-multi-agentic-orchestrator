"""Agent team orchestrator: builds execution plans for multi-agent wave execution."""

from __future__ import annotations

import yaml

from rapids_core.batch_dispatcher import build_feature_prompt


def parse_agent_definition(agent_md_content: str) -> dict:
    """Parse an agent markdown definition file's YAML frontmatter.

    Agent files like ``terraform-engineer.md`` have YAML frontmatter with
    fields: name, model, effort, phase, role, isolation, tools, description.

    Args:
        agent_md_content: Raw markdown content of an agent definition file.

    Returns:
        Dict with the parsed frontmatter fields. Returns an empty dict
        if no frontmatter is found.
    """
    content = agent_md_content.strip()
    if not content.startswith("---"):
        return {}

    # Split on --- delimiters
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}

    frontmatter = parts[1].strip()
    if not frontmatter:
        return {}

    try:
        parsed = yaml.safe_load(frontmatter)
        if not isinstance(parsed, dict):
            return {}
        return parsed
    except yaml.YAMLError:
        return {}


def resolve_generator_agent(
    feature_id: str,
    plugin: str,
    available_agents: list[dict],
) -> tuple[str, str]:
    """Resolve which generator agent should implement a feature.

    Matches the feature's plugin to available agent definitions.
    Falls back to ``rapids-lead`` if no domain-specific agent is found.

    Args:
        feature_id: The feature ID.
        plugin: The plugin name (e.g., "rapids-gcp").
        available_agents: List of agent definition dicts, each with keys
            like name, model, role, phase, plugin (optional).

    Returns:
        Tuple of ``(agent_name, model)``.
    """
    # Filter to coder agents in implement phase
    coders = [
        a for a in available_agents
        if a.get("role") == "coder" and a.get("phase") == "implement"
    ]

    if not coders:
        return ("rapids-lead", "opus")

    # Try to match by plugin
    if plugin:
        for agent in coders:
            agent_plugin = agent.get("plugin", "")
            if agent_plugin and plugin in agent_plugin:
                return (agent["name"], agent.get("model", "sonnet"))
            # Also check if agent name contains a plugin keyword
            if plugin.replace("rapids-", "") in agent.get("name", ""):
                return (agent["name"], agent.get("model", "sonnet"))

    # Fall back to first available coder
    return (coders[0]["name"], coders[0].get("model", "sonnet"))


def detect_coordination_needs(
    wave_features: list[str],
    dependency_graph: dict,
    feature_plugins: dict[str, str],
) -> list[str]:
    """Detect coordination requirements among features in a wave.

    Identifies cross-feature concerns that the lead agent should manage.

    Args:
        wave_features: Feature IDs in this wave.
        dependency_graph: Full dependency graph dict.
        feature_plugins: Feature to plugin mapping.

    Returns:
        List of human-readable coordination notes.
    """
    notes: list[str] = []
    wave_set = set(wave_features)

    # Check for multi-plugin coordination
    plugins_in_wave: dict[str, list[str]] = {}
    for fid in wave_features:
        plugin = feature_plugins.get(fid, "default")
        plugins_in_wave.setdefault(plugin, []).append(fid)

    if len(plugins_in_wave) > 1:
        plugin_summary = ", ".join(
            f"{plugin} ({', '.join(fids)})"
            for plugin, fids in sorted(plugins_in_wave.items())
        )
        notes.append(
            f"Multi-plugin coordination needed: {plugin_summary}. "
            f"Lead agent should coordinate API contracts and shared interfaces."
        )

    # Check for intra-wave dependencies
    dependencies = dependency_graph.get("dependencies", {})
    intra_wave_deps = []
    for fid in wave_features:
        deps = set(dependencies.get(fid, []))
        overlap = deps & wave_set
        if overlap:
            intra_wave_deps.append(f"{fid} depends on {', '.join(sorted(overlap))}")

    if intra_wave_deps:
        notes.append(
            f"Intra-wave dependencies detected: {'; '.join(intra_wave_deps)}. "
            f"Lead agent should sequence these features within the wave."
        )

    # Check for features that share the same plugin (potential file conflicts)
    for plugin, fids in plugins_in_wave.items():
        if len(fids) > 1 and plugin != "default":
            notes.append(
                f"Features {', '.join(sorted(fids))} share plugin {plugin}. "
                f"Lead agent should watch for file conflicts in shared directories."
            )

    return notes


def create_agent_team_plan(
    wave_number: int,
    wave_features: list[str],
    feature_specs: dict[str, str],
    feature_plugins: dict[str, str] | None = None,
    available_agents: list[dict] | None = None,
    dependency_graph: dict | None = None,
    accumulated_context: dict | None = None,
    evaluator_template: str = "",
    project_id: str = "",
    max_retries: int = 3,
) -> dict:
    """Create an agent team execution plan for a wave.

    This is the main entry point. It resolves generator agents for each
    feature, builds prompts, detects coordination needs, and produces
    the complete assignment plan.

    Args:
        wave_number: 1-indexed wave number.
        wave_features: Feature IDs in this wave.
        feature_specs: Map of feature ID to XML spec string.
        feature_plugins: Map of feature ID to plugin name.
        available_agents: Agent definitions from plugin agent directories.
        dependency_graph: Full dependency graph dict.
        accumulated_context: Shared project context.
        evaluator_template: Evaluator prompt template.
        project_id: Project identifier.
        max_retries: Maximum evaluator retry cycles.

    Returns:
        Dict representation of the agent team plan::

            {
                "wave_number": 1,
                "lead_agent": "rapids-lead",
                "assignments": [...],
                "total_features": 3,
                "execution_mode": "agent_teams",
                "coordination_notes": [...],
                "confirmation_required": True
            }

    Raises:
        ValueError: If wave_features is empty or feature specs are missing.
    """
    if not wave_features:
        raise ValueError("wave_features must not be empty")

    if feature_plugins is None:
        feature_plugins = {}
    if available_agents is None:
        available_agents = []
    if dependency_graph is None:
        dependency_graph = {"features": wave_features, "dependencies": {}}

    # Detect coordination needs
    coordination_notes = detect_coordination_needs(
        wave_features, dependency_graph, feature_plugins
    )

    # Resolve model tiers: evaluator should be higher than generator
    MODEL_TIERS = {"haiku": 0, "sonnet": 1, "opus": 2}
    TIER_UP = {"haiku": "sonnet", "sonnet": "opus", "opus": "opus"}

    assignments = []
    for feature_id in sorted(wave_features):
        spec_xml = feature_specs.get(feature_id)
        if spec_xml is None:
            raise ValueError(f"Missing feature spec for {feature_id}")

        plugin = feature_plugins.get(feature_id, "")
        gen_name, gen_model = resolve_generator_agent(
            feature_id, plugin, available_agents
        )

        # Evaluator model is one tier above the generator
        eval_model = TIER_UP.get(gen_model, "opus")

        prompt = build_feature_prompt(
            feature_xml=spec_xml,
            accumulated_context=accumulated_context,
            evaluator_template=evaluator_template,
            project_id=project_id,
        )

        branch_prefix = f"rapids/{project_id}/" if project_id else "rapids/"
        worktree_branch = f"{branch_prefix}{feature_id}"

        assignments.append({
            "feature_id": feature_id,
            "generator_agent": gen_name,
            "generator_model": gen_model,
            "evaluator_agent": "rapids-evaluator",
            "evaluator_model": eval_model,
            "worktree_branch": worktree_branch,
            "prompt": prompt,
            "plugin": plugin,
            "max_retries": max_retries,
        })

    return {
        "wave_number": wave_number,
        "lead_agent": "rapids-lead",
        "assignments": assignments,
        "total_features": len(assignments),
        "execution_mode": "agent_teams",
        "coordination_notes": coordination_notes,
        "confirmation_required": True,
    }


# ─── CLI entry point ──────────────────────────────────────────────────────────

def main() -> None:
    """CLI interface for agent team plan generation."""
    import json
    import sys

    try:
        config = json.load(sys.stdin)
        plan = create_agent_team_plan(
            wave_number=config["wave_number"],
            wave_features=config["wave_features"],
            feature_specs=config["feature_specs"],
            feature_plugins=config.get("feature_plugins", {}),
            available_agents=config.get("available_agents", []),
            dependency_graph=config.get("dependency_graph"),
            accumulated_context=config.get("accumulated_context"),
            evaluator_template=config.get("evaluator_template", ""),
            project_id=config.get("project_id", ""),
            max_retries=config.get("max_retries", 3),
        )
        json.dump(plan, sys.stdout, indent=2)
        print()
    except (KeyError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
