"""Dependency graph generator: parses feature spec XMLs to produce dependency-graph.json."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

from rapids_core.artifact_validator import validate_dependency_graph


@dataclass
class FeatureMetadata:
    """Parsed metadata from a single feature spec XML."""

    feature_id: str
    depends_on: list[str]
    plugin: str = ""
    name: str = ""
    priority: str = ""
    complexity: str = ""


def parse_feature_spec(xml_string: str) -> FeatureMetadata:
    """Parse a single feature spec XML and extract dependency metadata.

    Args:
        xml_string: Raw XML content of a feature spec file.

    Returns:
        FeatureMetadata with id, depends_on list, plugin, name, priority, complexity.

    Raises:
        ValueError: If the XML is malformed or missing the required ``id`` attribute.
    """
    try:
        root = ElementTree.fromstring(xml_string)
    except ElementTree.ParseError as e:
        raise ValueError(f"XML parse error: {e}") from e

    if root.tag != "feature":
        raise ValueError(f"Root element must be 'feature', got '{root.tag}'")

    feature_id = root.attrib.get("id")
    if not feature_id:
        raise ValueError("Feature spec missing required 'id' attribute")

    # Parse depends_on: comma or space-separated, strip whitespace
    depends_on_raw = root.attrib.get("depends_on", "")
    depends_on = [
        dep.strip()
        for dep in depends_on_raw.replace(",", " ").split()
        if dep.strip()
    ]

    plugin = root.attrib.get("plugin", "")
    priority = root.attrib.get("priority", "")

    name_elem = root.find("n")
    name = (name_elem.text or "").strip() if name_elem is not None else ""

    complexity_elem = root.find("estimated_complexity")
    complexity = (complexity_elem.text or "").strip() if complexity_elem is not None else ""

    return FeatureMetadata(
        feature_id=feature_id,
        depends_on=depends_on,
        plugin=plugin,
        name=name,
        priority=priority,
        complexity=complexity,
    )


def generate_dependency_graph(feature_specs: list[str]) -> dict:
    """Generate a dependency graph from a list of feature spec XML strings.

    Args:
        feature_specs: List of raw XML strings, one per feature spec file.

    Returns:
        Dict matching dependency-graph.json schema::

            {
                "features": ["F001", "F002", ...],
                "dependencies": {"F002": ["F001"], ...},
                "metadata": {
                    "F001": {"plugin": "gcp", "name": "...", "priority": "high", "complexity": "M"},
                    ...
                }
            }

    Raises:
        ValueError: If no specs provided, duplicate feature IDs found,
                    depends_on references unknown features, or validation fails.
    """
    if not feature_specs:
        raise ValueError("No feature specs provided")

    parsed: list[FeatureMetadata] = []
    for spec in feature_specs:
        parsed.append(parse_feature_spec(spec))

    # Check for duplicate IDs
    ids = [fm.feature_id for fm in parsed]
    if len(ids) != len(set(ids)):
        dupes = [fid for fid in ids if ids.count(fid) > 1]
        raise ValueError(f"Duplicate feature IDs: {sorted(set(dupes))}")

    feature_set = set(ids)

    # Build graph
    features = sorted(ids)
    dependencies: dict[str, list[str]] = {}
    metadata: dict[str, dict] = {}

    for fm in parsed:
        # Validate dependency targets exist
        for dep in fm.depends_on:
            if dep not in feature_set:
                raise ValueError(
                    f"Feature '{fm.feature_id}' depends on '{dep}', "
                    f"which is not in the feature set"
                )

        if fm.depends_on:
            dependencies[fm.feature_id] = sorted(fm.depends_on)

        metadata[fm.feature_id] = {
            "plugin": fm.plugin,
            "name": fm.name,
            "priority": fm.priority,
            "complexity": fm.complexity,
        }

    graph = {
        "features": features,
        "dependencies": dependencies,
        "metadata": metadata,
    }

    # Validate using the existing validator
    result = validate_dependency_graph(graph)
    if not result.valid:
        raise ValueError(f"Generated dependency graph is invalid: {result.error}")

    return graph


def generate_dependency_graph_from_directory(plan_dir: str) -> dict:
    """Read all ``*.xml`` files from a directory and generate the dependency graph.

    Args:
        plan_dir: Path to directory containing feature spec XML files.

    Returns:
        Same dict as :func:`generate_dependency_graph`.

    Raises:
        FileNotFoundError: If directory does not exist.
        ValueError: If no XML files found, or if parsing/validation fails.
    """
    plan_path = Path(plan_dir)
    if not plan_path.is_dir():
        raise FileNotFoundError(f"Directory not found: {plan_dir}")

    xml_files = sorted(plan_path.glob("*.xml"))
    if not xml_files:
        raise ValueError(f"No XML files found in {plan_dir}")

    specs = []
    for xml_file in xml_files:
        specs.append(xml_file.read_text())

    return generate_dependency_graph(specs)


# ─── CLI entry point ──────────────────────────────────────────────────────────

def main() -> None:
    """CLI interface for dependency graph generation."""
    import json
    import sys

    plan_dir = sys.argv[1] if len(sys.argv) > 1 else ".rapids/phases/plan"

    try:
        graph = generate_dependency_graph_from_directory(plan_dir)
        json.dump(graph, sys.stdout, indent=2)
        print()
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
