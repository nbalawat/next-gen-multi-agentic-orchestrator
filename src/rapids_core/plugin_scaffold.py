"""Plugin scaffold generator: creates minimum viable RAPIDS domain plugins."""

from __future__ import annotations

import json
from pathlib import Path


def generate_plugin_scaffold(
    output_dir: str | Path,
    name: str,
    description: str = "",
    capabilities: dict | None = None,
) -> Path:
    """Generate a minimum viable RAPIDS domain plugin scaffold.

    Creates the 3-file minimum:
        - .claude-plugin/plugin.json
        - rapids.plugin.json
        - skills/<name>-implement/SKILL.md

    Args:
        output_dir: Parent directory to create the plugin in.
        name: Plugin name (e.g., "rapids-python").
        description: Plugin description.
        capabilities: Optional capabilities dict for rapids.plugin.json.

    Returns:
        Path to the created plugin directory.
    """
    output_dir = Path(output_dir)
    plugin_dir = output_dir / name
    plugin_dir.mkdir(parents=True, exist_ok=True)

    # .claude-plugin/plugin.json
    manifest_dir = plugin_dir / ".claude-plugin"
    manifest_dir.mkdir(exist_ok=True)
    manifest = {
        "name": name,
        "version": "1.0.0",
        "description": description or f"RAPIDS domain plugin: {name}",
    }
    (manifest_dir / "plugin.json").write_text(json.dumps(manifest, indent=2) + "\n")

    # rapids.plugin.json
    if capabilities is None:
        capabilities = {
            "implement": [
                {
                    "id": f"{name}-implement",
                    "description": f"Implementation guidance for {name}",
                }
            ]
        }
    rapids_meta = {
        "rapids_core_version": ">=1.0.0",
        "capabilities": capabilities,
        "config": {},
    }
    (plugin_dir / "rapids.plugin.json").write_text(json.dumps(rapids_meta, indent=2) + "\n")

    # skills/<name>-implement/SKILL.md
    skill_name = f"{name.replace('rapids-', '')}-implement"
    skill_dir = plugin_dir / "skills" / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)

    skill_content = f"""---
name: {skill_name}
description: >
  Use this skill during the RAPIDS implement phase for {name} projects.
  Provides implementation guidance and best practices.
---

# {name} Implementation

Provide implementation guidance here.

## Guidelines
- Follow project conventions
- Write real tests (no mocks)
- Commit after each acceptance criterion passes
"""
    (skill_dir / "SKILL.md").write_text(skill_content)

    return plugin_dir
