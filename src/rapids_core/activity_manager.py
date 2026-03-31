"""Activity manager: YAML-defined DAG pipelines within RAPIDS phases.

Activities are the work units within a phase. Each activity has typed inputs,
outputs, dependencies, and an optional gate flag. Activities from plugins are
merged into the core DAG with ID prefixing to avoid collisions.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from rapids_core.wave_computer import compute_waves

# Default location for core activity definitions
_ACTIVITIES_DIR = Path(__file__).parent.parent.parent / "rapids-core" / "activities"


def load_phase_activities(
    phase: str,
    activities_dir: str | Path | None = None,
    plugin_activities: dict[str, list[dict]] | None = None,
) -> list[dict]:
    """Load activities for a phase, merging core + plugin activities.

    Args:
        phase: Phase name (e.g., ``research``).
        activities_dir: Directory containing core activity YAML files.
            Defaults to ``rapids-core/activities/``.
        plugin_activities: Dict mapping plugin name to list of activity dicts.
            Plugin activity IDs are auto-prefixed with ``<plugin>:``.

    Returns:
        Merged list of activity dicts, each with at least:
        ``id``, ``name``, ``description``, ``inputs``, ``outputs``,
        ``depends_on``, ``gate``, ``agent``, ``model``, ``source``.

    Raises:
        FileNotFoundError: If the YAML file for the phase doesn't exist.
    """
    if activities_dir is None:
        activities_dir = _ACTIVITIES_DIR

    yaml_path = Path(activities_dir) / f"{phase}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"No activity definition for phase '{phase}' at {yaml_path}")

    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    activities = []
    for act in data.get("activities", []):
        act.setdefault("depends_on", [])
        act.setdefault("gate", False)
        act.setdefault("agent", "rapids-lead")
        act.setdefault("model", "sonnet")
        act.setdefault("inputs", [])
        act.setdefault("outputs", [])
        act["source"] = "core"
        activities.append(act)

    # Merge plugin activities
    if plugin_activities:
        for plugin_name, plugin_acts in plugin_activities.items():
            prefix = plugin_name.replace("rapids-", "")
            for act in plugin_acts:
                # Prefix the ID to avoid collisions
                act["id"] = f"{prefix}:{act['id']}"
                act.setdefault("depends_on", [])
                act.setdefault("gate", False)
                act.setdefault("agent", "rapids-lead")
                act.setdefault("model", "sonnet")
                act.setdefault("inputs", [])
                act.setdefault("outputs", [])
                act["source"] = plugin_name
                activities.append(act)

    return activities


def compute_activity_waves(activities: list[dict]) -> list[list[str]]:
    """Compute execution waves for activities using topological sort.

    Reuses the existing ``wave_computer.compute_waves()`` (Kahn's algorithm).

    Args:
        activities: List of activity dicts with ``id`` and ``depends_on``.

    Returns:
        List of waves, where each wave is a sorted list of activity IDs.
    """
    graph = {
        "features": [a["id"] for a in activities],
        "dependencies": {
            a["id"]: a["depends_on"]
            for a in activities
            if a.get("depends_on")
        },
    }
    return compute_waves(graph)


def initialize_activity_progress(
    phase: str,
    activities: list[dict],
    output_dir: str,
) -> dict:
    """Create an activity progress tracking file for a phase.

    Args:
        phase: Phase name.
        activities: List of activity dicts.
        output_dir: Directory to write the progress file to.

    Returns:
        The created progress dict.
    """
    progress = {
        "phase": phase,
        "activities": {
            a["id"]: {
                "name": a["name"],
                "status": "pending",
                "gate": a.get("gate", False),
                "source": a.get("source", "core"),
                "outputs": {},
                "started_at": None,
                "completed_at": None,
            }
            for a in activities
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    progress_file = out / f"activity-progress-{phase}.json"
    progress_file.write_text(json.dumps(progress, indent=2) + "\n")
    return progress


def read_activity_progress(progress_file: str) -> dict:
    """Read an activity progress file.

    Args:
        progress_file: Path to the progress JSON file.

    Returns:
        The progress dict.
    """
    return json.loads(Path(progress_file).read_text())


def update_activity_status(
    progress_file: str,
    activity_id: str,
    status: str,
    outputs: dict[str, str] | None = None,
) -> dict:
    """Update an activity's status in the progress file.

    Args:
        progress_file: Path to the progress JSON file.
        activity_id: The activity ID to update.
        status: New status (``pending``, ``in_progress``, ``complete``).
        outputs: Dict mapping output name to file path (for completed activities).

    Returns:
        The updated progress dict.

    Raises:
        ValueError: If activity_id not found.
    """
    path = Path(progress_file)
    progress = json.loads(path.read_text())

    if activity_id not in progress["activities"]:
        raise ValueError(f"Activity '{activity_id}' not found")

    act = progress["activities"][activity_id]
    now = datetime.now(timezone.utc).isoformat()

    act["status"] = status
    if status == "in_progress" and act["started_at"] is None:
        act["started_at"] = now
    elif status == "complete":
        act["completed_at"] = now
        if outputs:
            act["outputs"] = outputs

    path.write_text(json.dumps(progress, indent=2) + "\n")
    return progress


def get_activity_inputs(
    activity: dict,
    progress: dict,
    phase_dir: str,
) -> dict[str, str | None]:
    """Resolve an activity's inputs from completed prior activities.

    Args:
        activity: The activity dict.
        progress: The progress dict.
        phase_dir: Path to the phase artifacts directory.

    Returns:
        Dict mapping input name to resolved file path (or None if not available).
    """
    resolved = {}
    for inp in activity.get("inputs", []):
        name = inp["name"]
        source = inp.get("from")
        if source and source in progress.get("activities", {}):
            source_act = progress["activities"][source]
            if source_act["status"] == "complete":
                # Look up the output file
                resolved[name] = source_act.get("outputs", {}).get(name)
            else:
                resolved[name] = None
        elif inp.get("source") == "user":
            resolved[name] = "(user-provided)"
        elif inp.get("source") == "previous_phase":
            # Try to find the file in the phase directory
            resolved[name] = f"{phase_dir}/{name}.md"
        else:
            resolved[name] = None
    return resolved


def check_phase_gate(progress_file: str) -> bool:
    """Check if all gate activities in a phase are complete.

    Args:
        progress_file: Path to the activity progress JSON file.

    Returns:
        True if all activities with ``gate: true`` have status ``complete``.
    """
    progress = json.loads(Path(progress_file).read_text())
    for act_id, act in progress.get("activities", {}).items():
        if act.get("gate") and act.get("status") != "complete":
            return False
    return True


def format_activity_checklist(
    activities: list[dict],
    progress: dict | None = None,
) -> str:
    """Format activities as an ASCII checklist with status icons.

    Args:
        activities: List of activity dicts.
        progress: Optional progress dict. If None, all show as pending.

    Returns:
        Formatted checklist string.
    """
    if not activities:
        return "  No activities defined.\n"

    act_progress = progress.get("activities", {}) if progress else {}

    lines = []
    for act in activities:
        act_id = act["id"]
        name = act["name"]
        gate = act.get("gate", False)
        source = act.get("source", "core")
        deps = act.get("depends_on", [])
        outputs = [o.get("file", "?") for o in act.get("outputs", [])]
        output_str = ", ".join(outputs) if outputs else "—"

        ap = act_progress.get(act_id, {})
        status = ap.get("status", "pending")

        if status == "complete":
            icon = "✓"
        elif status == "in_progress":
            icon = "→"
        else:
            icon = "○"

        gate_marker = " (gate)" if gate else ""
        source_marker = f" [{source}]" if source != "core" else ""

        lines.append(f"  {icon} [{act_id}] {name}{gate_marker}{source_marker}")
        lines.append(f"       Output: {output_str}")

        if deps:
            dep_statuses = []
            for dep in deps:
                dep_ap = act_progress.get(dep, {})
                dep_status = dep_ap.get("status", "pending")
                dep_icon = "✓" if dep_status == "complete" else "○"
                dep_statuses.append(f"{dep_icon} {dep}")
            lines.append(f"       Depends: {', '.join(dep_statuses)}")

        lines.append("")

    return "\n".join(lines)
