"""Work item manager: concurrent bug fixes, features, and enhancements within a project.

A work item is a unit of work with its own tier, phase sequence, and lifecycle.
Projects become containers for multiple work items that can progress independently.
"""

from __future__ import annotations

from datetime import datetime, timezone

from rapids_core.phase_router import route_phases
from rapids_core.scope_classifier import classify_scope


WORK_ITEM_TYPES = ("bug", "enhancement", "feature", "refactor")


def migrate_rapids_json(config: dict) -> dict:
    """Auto-migrate old rapids.json format to support work items.

    Old format has ``scope.tier``, ``scope.phases``, ``current.phase``.
    New format wraps these into a ``work_items`` array.

    Args:
        config: The rapids.json dict (may be old or new format).

    Returns:
        The config dict in new format, with ``work_items`` array.
        If already in new format, returns unchanged.
    """
    if "work_items" in config:
        return config

    # Extract old values
    scope = config.get("scope", {})
    tier = scope.get("tier", 3)
    phases = scope.get("phases", route_phases(tier))
    current_phase = config.get("current", {}).get("phase", phases[0] if phases else "implement")
    project_id = config.get("project", {}).get("id", "unknown")

    # Create the first work item from existing state
    work_item = {
        "id": "WI-001",
        "title": project_id,
        "type": "feature",
        "tier": tier,
        "phases": phases,
        "current_phase": current_phase,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    config["work_items"] = [work_item]
    config["active_work_item"] = "WI-001"

    # Keep scope as defaults for new work items
    config["scope"] = {
        "default_tier": tier,
        "default_phases": phases,
    }

    # Remove old current.phase (now per-item)
    # Keep current dict for backward compat but phase comes from work item
    config["current"] = {"phase": current_phase}

    return config


def next_work_item_id(config: dict) -> str:
    """Generate the next work item ID (WI-NNN).

    Args:
        config: The rapids.json dict (must be in new format).

    Returns:
        Next available ID like ``WI-002``.
    """
    items = config.get("work_items", [])
    if not items:
        return "WI-001"

    max_num = 0
    for item in items:
        item_id = item.get("id", "")
        if item_id.startswith("WI-"):
            try:
                num = int(item_id[3:])
                max_num = max(max_num, num)
            except ValueError:
                pass

    return f"WI-{max_num + 1:03d}"


def create_work_item(
    config: dict,
    title: str,
    item_type: str,
    scope_signals: dict | None = None,
    tier: int | None = None,
) -> dict:
    """Create a new work item and add it to the config.

    Either provide ``scope_signals`` (auto-classify tier) or ``tier`` directly.

    Args:
        config: The rapids.json dict (new format).
        title: Description of the work item.
        item_type: One of "bug", "enhancement", "feature", "refactor".
        scope_signals: Signals for the scope classifier.
        tier: Explicit tier (1-5). Overrides scope_signals.

    Returns:
        The created work item dict.

    Raises:
        ValueError: If item_type is invalid or neither scope_signals nor tier provided.
    """
    if item_type not in WORK_ITEM_TYPES:
        raise ValueError(
            f"Invalid work item type '{item_type}'. Must be one of {WORK_ITEM_TYPES}"
        )

    if tier is None and scope_signals is None:
        raise ValueError("Either scope_signals or tier must be provided")

    if tier is None:
        result = classify_scope(scope_signals)
        tier = result.tier

    phases = route_phases(tier)
    item_id = next_work_item_id(config)

    work_item = {
        "id": item_id,
        "title": title,
        "type": item_type,
        "tier": tier,
        "phases": phases,
        "current_phase": phases[0],
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if "work_items" not in config:
        config = migrate_rapids_json(config)

    config["work_items"].append(work_item)
    config["active_work_item"] = item_id

    # Update current.phase to reflect the new active item
    config["current"] = {"phase": phases[0]}

    return work_item


def list_work_items(config: dict, active_only: bool = True) -> list[dict]:
    """List work items in the config.

    Args:
        config: The rapids.json dict.
        active_only: If True, only return items with status 'active'.

    Returns:
        List of work item dicts.
    """
    config = migrate_rapids_json(config)
    items = config.get("work_items", [])
    if active_only:
        return [i for i in items if i.get("status") == "active"]
    return items


def get_work_item(config: dict, work_item_id: str) -> dict | None:
    """Get a specific work item by ID.

    Args:
        config: The rapids.json dict.
        work_item_id: The work item ID (e.g., "WI-001").

    Returns:
        The work item dict, or None if not found.
    """
    config = migrate_rapids_json(config)
    for item in config.get("work_items", []):
        if item["id"] == work_item_id:
            return item
    return None


def get_active_work_item(config: dict) -> dict | None:
    """Get the currently active work item.

    Args:
        config: The rapids.json dict.

    Returns:
        The active work item dict, or None if none active.
    """
    config = migrate_rapids_json(config)
    active_id = config.get("active_work_item")
    if active_id:
        return get_work_item(config, active_id)
    # Fall back to first active item
    active_items = list_work_items(config, active_only=True)
    return active_items[0] if active_items else None


def switch_work_item(config: dict, work_item_id: str) -> dict:
    """Switch the active work item.

    Args:
        config: The rapids.json dict.
        work_item_id: The work item ID to switch to.

    Returns:
        The updated config dict.

    Raises:
        ValueError: If work item not found.
    """
    config = migrate_rapids_json(config)
    item = get_work_item(config, work_item_id)
    if item is None:
        raise ValueError(f"Work item {work_item_id} not found")

    config["active_work_item"] = work_item_id
    config["current"] = {"phase": item["current_phase"]}

    return config


def advance_work_item_phase(config: dict, work_item_id: str) -> dict | None:
    """Advance a work item to its next phase.

    Args:
        config: The rapids.json dict.
        work_item_id: The work item ID to advance.

    Returns:
        The updated work item dict, or None if already at last phase.

    Raises:
        ValueError: If work item not found.
    """
    config = migrate_rapids_json(config)
    item = get_work_item(config, work_item_id)
    if item is None:
        raise ValueError(f"Work item {work_item_id} not found")

    phases = item["phases"]
    current = item["current_phase"]

    try:
        idx = phases.index(current)
    except ValueError:
        return None

    if idx >= len(phases) - 1:
        return None  # Already at last phase

    next_phase = phases[idx + 1]
    item["current_phase"] = next_phase

    # If this is the active item, update current.phase too
    if config.get("active_work_item") == work_item_id:
        config["current"] = {"phase": next_phase}

    return item


def complete_work_item(config: dict, work_item_id: str) -> dict:
    """Mark a work item as complete.

    Args:
        config: The rapids.json dict.
        work_item_id: The work item ID to complete.

    Returns:
        The updated work item dict.

    Raises:
        ValueError: If work item not found.
    """
    config = migrate_rapids_json(config)
    item = get_work_item(config, work_item_id)
    if item is None:
        raise ValueError(f"Work item {work_item_id} not found")

    item["status"] = "complete"
    item["completed_at"] = datetime.now(timezone.utc).isoformat()

    # If this was the active item, switch to next active one
    if config.get("active_work_item") == work_item_id:
        active_items = [i for i in config.get("work_items", []) if i.get("status") == "active"]
        if active_items:
            config["active_work_item"] = active_items[0]["id"]
            config["current"] = {"phase": active_items[0]["current_phase"]}
        else:
            config["active_work_item"] = None

    return item


def format_work_items_table(items: list[dict], active_id: str | None = None) -> str:
    """Format work items as a display table.

    Args:
        items: List of work item dicts.
        active_id: The currently active work item ID (highlighted).

    Returns:
        Formatted table string.
    """
    if not items:
        return "  No work items.\n"

    lines = []
    lines.append(f"  {'ID':<8} {'TYPE':<14} {'TIER':<6} {'PHASE':<14} {'STATUS':<10} TITLE")
    lines.append("  " + "─" * 72)

    for item in items:
        marker = "▶" if item["id"] == active_id else " "
        status_icon = "●" if item.get("status") == "active" else "✓" if item.get("status") == "complete" else "○"
        title = item.get("title", "")[:30]
        lines.append(
            f" {marker}{item['id']:<8} {item.get('type','?'):<14} T{item['tier']:<5} "
            f"{item.get('current_phase','?'):<14} {status_icon} {item.get('status','?'):<8} {title}"
        )

    lines.append("  " + "─" * 72)
    return "\n".join(lines) + "\n"
