"""Config loader: normalizes rapids.json to the canonical format.

Handles multiple rapids.json formats that may be created by Claude
improvising the structure. Always returns the canonical nested format.
"""

from __future__ import annotations

import json
from pathlib import Path

from rapids_core.phase_router import route_phases


def load_rapids_config(rapids_dir: str) -> dict:
    """Load and normalize rapids.json to the canonical format.

    Handles both the canonical nested format and flat formats created
    by Claude during project initialization.

    Canonical format::

        {
            "project": {"id": "my-project"},
            "scope": {"tier": 3, "phases": ["analysis", "plan", "implement", "deploy"]},
            "current": {"phase": "analysis"},
            "work_items": [...],
            "active_work_item": "WI-001",
            "plugins": []
        }

    Also handles flat formats like::

        {"tier": 3, "current_phase": "analysis", "project_name": "my-project", ...}

    Args:
        rapids_dir: Path to the ``.rapids/`` directory.

    Returns:
        Normalized config dict in canonical format.
    """
    rapids_json = Path(rapids_dir) / "rapids.json"
    if not rapids_json.exists():
        return {}

    config = json.loads(rapids_json.read_text())
    return normalize_config(config)


def normalize_config(config: dict) -> dict:
    """Normalize a rapids.json config dict to canonical format.

    Args:
        config: Raw config dict (any format).

    Returns:
        Config in canonical nested format.
    """
    # Already canonical format
    if "scope" in config and "current" in config and "project" in config:
        return config

    # Extract values from whatever format we have
    tier = (
        config.get("scope", {}).get("tier")
        or config.get("tier")
        or 3
    )
    tier = int(tier)

    phase = (
        config.get("current", {}).get("phase")
        or config.get("current_phase")
        or config.get("phase")
        or "implement"
    )

    project_id = (
        config.get("project", {}).get("id")
        or config.get("project_name")
        or config.get("project_id")
        or config.get("name")
        or "unknown"
    )

    phases = (
        config.get("scope", {}).get("phases")
        or config.get("phases")
        or route_phases(tier)
    )

    plugins = config.get("plugins", [])
    work_items = config.get("work_items", [])
    active_work_item = config.get("active_work_item")

    # Build canonical format
    canonical = {
        "project": {"id": project_id},
        "scope": {"tier": tier, "phases": phases},
        "current": {"phase": phase},
        "plugins": plugins,
    }

    # Preserve work items if present
    if work_items:
        canonical["work_items"] = work_items
    if active_work_item:
        canonical["active_work_item"] = active_work_item

    # Preserve any extra fields
    for key in ("workspace", "execution_mode", "description", "status",
                "created_at", "tier_label", "active_persona"):
        if key in config:
            canonical[key] = config[key]

    return canonical


def save_rapids_config(rapids_dir: str, config: dict) -> None:
    """Save a normalized config to rapids.json.

    Args:
        rapids_dir: Path to the ``.rapids/`` directory.
        config: The config dict (will be normalized before saving).
    """
    canonical = normalize_config(config)
    rapids_json = Path(rapids_dir) / "rapids.json"
    rapids_json.write_text(json.dumps(canonical, indent=2) + "\n")
