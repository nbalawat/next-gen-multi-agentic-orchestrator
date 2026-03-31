"""Batch dispatcher: builds dispatch plans for /batch execution of independent features."""

from __future__ import annotations

from rapids_core.dependency_graph_generator import parse_feature_spec


def build_feature_prompt(
    feature_xml: str,
    accumulated_context: dict | None = None,
    evaluator_template: str = "",
    project_id: str = "",
) -> str:
    """Build the complete prompt for a batch worker implementing a single feature.

    The prompt includes the feature spec, context, Generator pattern instructions,
    and the evaluator template for self-checking.

    Args:
        feature_xml: Raw XML of the feature spec.
        accumulated_context: Project context dict from accumulated.json.
        evaluator_template: Evaluator prompt template for self-verification.
        project_id: Project identifier for branch naming.

    Returns:
        Complete prompt string for the batch worker.
    """
    meta = parse_feature_spec(feature_xml)

    # Extract acceptance criteria from XML
    from xml.etree import ElementTree

    root = ElementTree.fromstring(feature_xml)
    criteria = []
    ac_elem = root.find("acceptance_criteria")
    if ac_elem is not None:
        for criterion in ac_elem.findall("criterion"):
            if criterion.text and criterion.text.strip():
                criteria.append(criterion.text.strip())

    desc_elem = root.find("description")
    description = (desc_elem.text or "").strip() if desc_elem is not None else ""

    # Build structured prompt
    lines = [
        f"# Implement Feature {meta.feature_id}: {meta.name}",
        "",
        f"**Priority:** {meta.priority} | **Complexity:** {meta.complexity or 'unspecified'}",
        "",
        "## Description",
        "",
        description,
        "",
        "## Acceptance Criteria",
        "",
        "Implement these one at a time. After each criterion passes, commit and update "
        "feature-progress.json before moving to the next.",
        "",
    ]

    for i, criterion in enumerate(criteria, 1):
        lines.append(f"{i}. {criterion}")
    lines.append("")

    # Add accumulated context if provided
    if accumulated_context:
        lines.append("## Project Context")
        lines.append("")
        key_decisions = accumulated_context.get("key_decisions", [])
        if key_decisions:
            lines.append("### Key Decisions")
            for decision in key_decisions:
                lines.append(f"- {decision}")
            lines.append("")
        constraints = accumulated_context.get("constraints", [])
        if constraints:
            lines.append("### Constraints")
            for constraint in constraints:
                lines.append(f"- {constraint}")
            lines.append("")

    # Generator pattern instructions
    lines.extend([
        "## Implementation Rules (Generator Pattern)",
        "",
        "1. Work through acceptance criteria ONE AT A TIME",
        "2. For each criterion:",
        "   a. Write the implementation code",
        "   b. Write real tests (no mocks) that verify the criterion",
        "   c. Run the tests and ensure they pass",
        "   d. Commit with a descriptive message: `feat({fid}): <criterion summary>`".format(
            fid=meta.feature_id
        ),
        "   e. Update `.rapids/phases/implement/feature-progress-{fid}.json`".format(
            fid=meta.feature_id
        ),
        "3. After all criteria pass, mark the feature as complete in feature-progress",
        "",
    ])

    # Add evaluator template if provided
    if evaluator_template:
        lines.extend([
            "## Self-Verification (Evaluator Checklist)",
            "",
            evaluator_template.strip(),
            "",
        ])

    return "\n".join(lines)


def create_batch_dispatch_plan(
    wave_number: int,
    wave_features: list[str],
    feature_specs: dict[str, str],
    feature_plugins: dict[str, str] | None = None,
    accumulated_context: dict | None = None,
    evaluator_template: str = "",
    project_id: str = "",
) -> dict:
    """Create a batch dispatch plan for a wave of independent features.

    Args:
        wave_number: 1-indexed wave number.
        wave_features: List of feature IDs in this wave.
        feature_specs: Map of feature ID to its raw XML spec string.
        feature_plugins: Map of feature ID to plugin name.
        accumulated_context: Shared project context.
        evaluator_template: Evaluator prompt template.
        project_id: Project identifier.

    Returns:
        Dict with dispatch plan::

            {
                "wave_number": 1,
                "total_features": 3,
                "execution_mode": "batch",
                "confirmation_required": True,
                "tasks": [...]
            }

    Raises:
        ValueError: If wave_features is empty or a feature_id is missing from feature_specs.
    """
    if not wave_features:
        raise ValueError("wave_features must not be empty")

    if feature_plugins is None:
        feature_plugins = {}

    tasks = []
    for feature_id in sorted(wave_features):
        spec_xml = feature_specs.get(feature_id)
        if spec_xml is None:
            raise ValueError(f"Missing feature spec for {feature_id}")

        prompt = build_feature_prompt(
            feature_xml=spec_xml,
            accumulated_context=accumulated_context,
            evaluator_template=evaluator_template,
            project_id=project_id,
        )

        branch_prefix = f"rapids/{project_id}/" if project_id else "rapids/"
        worktree_branch = f"{branch_prefix}{feature_id}"

        context_files = [
            ".rapids/context/accumulated.json",
            f".rapids/phases/plan/{feature_id}.xml",
        ]

        tasks.append({
            "feature_id": feature_id,
            "prompt": prompt,
            "worktree_branch": worktree_branch,
            "context_files": context_files,
            "plugin": feature_plugins.get(feature_id, ""),
        })

    return {
        "wave_number": wave_number,
        "total_features": len(tasks),
        "execution_mode": "batch",
        "confirmation_required": True,
        "tasks": tasks,
    }


def format_batch_command(dispatch_plan: dict) -> str:
    """Format the dispatch plan into a ``/batch`` command string.

    Each task becomes a separate prompt block separated by ``---``.

    Args:
        dispatch_plan: Dict from :func:`create_batch_dispatch_plan`.

    Returns:
        Formatted string suitable for ``/batch`` invocation.
    """
    tasks = dispatch_plan.get("tasks", [])
    if not tasks:
        return ""

    blocks = []
    for task in tasks:
        blocks.append(task["prompt"])

    return "\n---\n".join(blocks)


# ─── CLI entry point ──────────────────────────────────────────────────────────

def main() -> None:
    """CLI interface for batch dispatch plan generation."""
    import json
    import sys

    try:
        config = json.load(sys.stdin)
        plan = create_batch_dispatch_plan(
            wave_number=config["wave_number"],
            wave_features=config["wave_features"],
            feature_specs=config["feature_specs"],
            feature_plugins=config.get("feature_plugins", {}),
            accumulated_context=config.get("accumulated_context"),
            evaluator_template=config.get("evaluator_template", ""),
            project_id=config.get("project_id", ""),
        )
        json.dump(plan, sys.stdout, indent=2)
        print()
    except (KeyError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
