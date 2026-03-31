"""Artifact validation: validates feature specs (XML) and dependency graphs (JSON)."""

from __future__ import annotations

import json
from xml.etree import ElementTree

from rapids_core.models import ValidationResult


def validate_feature_spec(xml_string: str) -> ValidationResult:
    """Validate a feature specification XML document.

    Required structure:
        <feature id="..." version="..." priority="..." depends_on="..." plugin="...">
            <n>Feature Name</n>
            <description>...</description>
            <acceptance_criteria>
                <criterion>...</criterion>
            </acceptance_criteria>
            <estimated_complexity>S|M|L|XL</estimated_complexity>
        </feature>

    Returns:
        ValidationResult indicating pass/fail with details.
    """
    warnings: list[str] = []

    try:
        root = ElementTree.fromstring(xml_string)
    except ElementTree.ParseError as e:
        return ValidationResult(valid=False, error=f"XML parse error: {e}")

    if root.tag != "feature":
        return ValidationResult(valid=False, error=f"Root element must be 'feature', got '{root.tag}'")

    # Required attributes
    required_attrs = ["id", "version", "priority"]
    for attr in required_attrs:
        if attr not in root.attrib:
            return ValidationResult(valid=False, error=f"Missing required attribute: {attr}")

    # Required child elements
    name_elem = root.find("n")
    if name_elem is None or not (name_elem.text and name_elem.text.strip()):
        return ValidationResult(valid=False, error="Missing or empty <n> (name) element")

    desc_elem = root.find("description")
    if desc_elem is None or not (desc_elem.text and desc_elem.text.strip()):
        return ValidationResult(valid=False, error="Missing or empty <description> element")

    # Acceptance criteria
    ac_elem = root.find("acceptance_criteria")
    if ac_elem is None:
        return ValidationResult(valid=False, error="Missing <acceptance_criteria> element")

    criteria = ac_elem.findall("criterion")
    if not criteria:
        return ValidationResult(
            valid=False, error="<acceptance_criteria> must contain at least one <criterion>"
        )

    for i, criterion in enumerate(criteria):
        if not (criterion.text and criterion.text.strip()):
            warnings.append(f"Criterion {i + 1} is empty")

    # Estimated complexity
    complexity_elem = root.find("estimated_complexity")
    if complexity_elem is not None:
        valid_complexities = {"S", "M", "L", "XL"}
        if complexity_elem.text and complexity_elem.text.strip() not in valid_complexities:
            warnings.append(
                f"estimated_complexity '{complexity_elem.text.strip()}' "
                f"is not one of {valid_complexities}"
            )

    # Priority validation
    valid_priorities = {"low", "medium", "high", "critical"}
    priority = root.attrib.get("priority", "")
    if priority and priority not in valid_priorities:
        warnings.append(f"Priority '{priority}' is not one of {valid_priorities}")

    return ValidationResult(valid=True, warnings=warnings)


def validate_dependency_graph(graph: dict) -> ValidationResult:
    """Validate a dependency graph structure.

    Required structure:
        {
            "features": ["F001", "F002", ...],
            "dependencies": {"F002": ["F001"], ...}
        }

    Returns:
        ValidationResult indicating pass/fail with details.
    """
    warnings: list[str] = []

    if not isinstance(graph, dict):
        return ValidationResult(valid=False, error="Dependency graph must be a dict")

    # Required keys
    if "features" not in graph:
        return ValidationResult(valid=False, error="Missing 'features' key")

    features = graph["features"]
    if not isinstance(features, list):
        return ValidationResult(valid=False, error="'features' must be a list")

    if not features:
        return ValidationResult(valid=False, error="'features' list must not be empty")

    # Check for duplicate features
    if len(features) != len(set(features)):
        return ValidationResult(valid=False, error="'features' list contains duplicates")

    feature_set = set(features)

    # Dependencies
    dependencies = graph.get("dependencies", {})
    if not isinstance(dependencies, dict):
        return ValidationResult(valid=False, error="'dependencies' must be a dict")

    for feature, deps in dependencies.items():
        if feature not in feature_set:
            warnings.append(f"Dependency key '{feature}' is not in the features list")

        if not isinstance(deps, list):
            return ValidationResult(
                valid=False, error=f"Dependencies for '{feature}' must be a list"
            )

        for dep in deps:
            if dep not in feature_set:
                return ValidationResult(
                    valid=False,
                    error=f"Feature '{feature}' depends on '{dep}', which is not in features list",
                )

            if dep == feature:
                return ValidationResult(
                    valid=False, error=f"Feature '{feature}' depends on itself"
                )

    return ValidationResult(valid=True, warnings=warnings)


def validate_journal_entry(entry: dict) -> ValidationResult:
    """Validate an audit journal entry.

    Required fields: ts, event, phase.

    Returns:
        ValidationResult indicating pass/fail with details.
    """
    if not isinstance(entry, dict):
        return ValidationResult(valid=False, error="Journal entry must be a dict")

    required_fields = ["ts", "event", "phase"]
    for field in required_fields:
        if field not in entry:
            return ValidationResult(valid=False, error=f"Missing required field: {field}")

    if not isinstance(entry["ts"], str) or not entry["ts"]:
        return ValidationResult(valid=False, error="'ts' must be a non-empty string")

    if not isinstance(entry["event"], str) or not entry["event"]:
        return ValidationResult(valid=False, error="'event' must be a non-empty string")

    return ValidationResult(valid=True)
