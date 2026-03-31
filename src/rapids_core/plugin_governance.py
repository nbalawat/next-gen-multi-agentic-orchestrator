"""Plugin governance: validates plugin structure and detects capability collisions."""

from __future__ import annotations

import json
import re
from pathlib import Path

from rapids_core.models import ValidationResult


def validate_plugin(plugin_path: str | Path) -> ValidationResult:
    """Validate a plugin directory conforms to the RAPIDS plugin contract.

    Checks:
        - .claude-plugin/plugin.json exists and has "name"
        - rapids.plugin.json (if present) has valid structure
        - Skills have SKILL.md files
        - No absolute directives in skill content

    Args:
        plugin_path: Path to the plugin directory.

    Returns:
        ValidationResult with validation outcome.
    """
    plugin_path = Path(plugin_path)
    warnings: list[str] = []

    # Check plugin directory exists
    if not plugin_path.is_dir():
        return ValidationResult(valid=False, error=f"Plugin directory not found: {plugin_path}")

    # Check .claude-plugin/plugin.json
    manifest_path = plugin_path / ".claude-plugin" / "plugin.json"
    if not manifest_path.is_file():
        return ValidationResult(
            valid=False, error="Missing .claude-plugin/plugin.json manifest"
        )

    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as e:
        return ValidationResult(valid=False, error=f"Invalid plugin.json: {e}")

    if "name" not in manifest:
        return ValidationResult(valid=False, error="plugin.json missing required 'name' field")

    # Check rapids.plugin.json (optional but validated if present)
    rapids_meta_path = plugin_path / "rapids.plugin.json"
    if rapids_meta_path.is_file():
        try:
            rapids_meta = json.loads(rapids_meta_path.read_text())
        except json.JSONDecodeError as e:
            return ValidationResult(valid=False, error=f"Invalid rapids.plugin.json: {e}")

        if "capabilities" in rapids_meta:
            caps = rapids_meta["capabilities"]
            if not isinstance(caps, dict):
                return ValidationResult(
                    valid=False, error="'capabilities' in rapids.plugin.json must be a dict"
                )

    # Validate skills directory (if present)
    skills_dir = plugin_path / "skills"
    if skills_dir.is_dir():
        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_md = skill_dir / "SKILL.md"
                if not skill_md.is_file():
                    warnings.append(f"Skill directory '{skill_dir.name}' missing SKILL.md")
                else:
                    # Check for absolute directives
                    content = skill_md.read_text()
                    abs_patterns = [
                        r"\bYou MUST always\b",
                        r"\bALWAYS use\b",
                        r"\bNEVER use\b",
                        r"\bYou MUST NEVER\b",
                    ]
                    for pattern in abs_patterns:
                        if re.search(pattern, content):
                            warnings.append(
                                f"Skill '{skill_dir.name}' contains absolute directive "
                                f"matching '{pattern}' — consider softer guidance"
                            )

    # Validate agents directory (if present)
    agents_dir = plugin_path / "agents"
    if agents_dir.is_dir():
        for agent_file in agents_dir.glob("*.md"):
            content = agent_file.read_text()
            if not content.strip():
                warnings.append(f"Agent file '{agent_file.name}' is empty")

    return ValidationResult(valid=True, warnings=warnings)


def detect_capability_collisions(
    new_plugin_path: str | Path,
    existing_plugins: list[str | Path],
) -> list[dict]:
    """Detect capability ID collisions between a new plugin and existing ones.

    Args:
        new_plugin_path: Path to the new plugin.
        existing_plugins: Paths to existing installed plugins.

    Returns:
        List of collision dicts with keys: capability_id, new_plugin, existing_plugin, phase.
    """
    new_caps = _extract_capabilities(Path(new_plugin_path))
    collisions: list[dict] = []

    for existing_path in existing_plugins:
        existing_caps = _extract_capabilities(Path(existing_path))
        for phase, cap_ids in new_caps.items():
            for cap_id in cap_ids:
                if cap_id in existing_caps.get(phase, set()):
                    collisions.append(
                        {
                            "capability_id": cap_id,
                            "new_plugin": Path(new_plugin_path).name,
                            "existing_plugin": Path(existing_path).name,
                            "phase": phase,
                        }
                    )

    return collisions


def _extract_capabilities(plugin_path: Path) -> dict[str, set[str]]:
    """Extract capability IDs from a plugin's rapids.plugin.json."""
    rapids_meta_path = plugin_path / "rapids.plugin.json"
    if not rapids_meta_path.is_file():
        return {}

    try:
        meta = json.loads(rapids_meta_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}

    caps = meta.get("capabilities", {})
    result: dict[str, set[str]] = {}
    for phase, cap_list in caps.items():
        if isinstance(cap_list, list):
            result[phase] = {c["id"] for c in cap_list if isinstance(c, dict) and "id" in c}

    return result
