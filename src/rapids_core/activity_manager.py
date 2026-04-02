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


def select_activities(
    activities: list[dict],
    tier: int,
    item_type: str = "feature",
) -> list[dict]:
    """Filter activities based on work item context using ``when`` conditions.

    Each activity can have a ``when`` dict with these optional fields:

    - ``required``: If True, always included regardless of tier/type.
    - ``min_tier``: Minimum tier required (activity skipped if tier < min_tier).
    - ``max_tier``: Maximum tier allowed (activity skipped if tier > max_tier).
    - ``types``: List of work item types this applies to (e.g., ``["feature", "refactor"]``).

    Activities without a ``when`` clause are always included.

    When an activity is pruned, its dependents have the pruned activity's
    ``depends_on`` inherited (dependency re-wiring). This keeps the DAG valid.

    Args:
        activities: Full list of activity dicts (from ``load_phase_activities``).
        tier: The work item's scope tier (1-5).
        item_type: The work item type (``bug``, ``enhancement``, ``feature``, ``refactor``).

    Returns:
        Filtered list of activity dicts with dependencies re-wired.
    """
    # First pass: determine which activities are included
    included_ids: set[str] = set()
    excluded_ids: set[str] = set()
    activity_map: dict[str, dict] = {}

    for act in activities:
        activity_map[act["id"]] = act
        when = act.get("when")

        if when is None:
            # No condition → always included
            included_ids.add(act["id"])
            continue

        if when.get("required"):
            included_ids.add(act["id"])
            continue

        min_tier = when.get("min_tier", 1)
        max_tier = when.get("max_tier", 5)
        allowed_types = when.get("types")

        if tier < min_tier or tier > max_tier:
            excluded_ids.add(act["id"])
            continue

        if allowed_types and item_type not in allowed_types:
            excluded_ids.add(act["id"])
            continue

        included_ids.add(act["id"])

    # Second pass: re-wire dependencies around excluded activities
    # If A depends on B, and B is excluded but B depended on C,
    # then A should now depend on C directly.
    def resolve_deps(dep_ids: list[str]) -> list[str]:
        resolved: list[str] = []
        for dep_id in dep_ids:
            if dep_id in included_ids:
                resolved.append(dep_id)
            elif dep_id in activity_map:
                # Excluded: inherit its dependencies
                parent_deps = activity_map[dep_id].get("depends_on", [])
                resolved.extend(resolve_deps(parent_deps))
        return resolved

    result = []
    for act in activities:
        if act["id"] not in included_ids:
            continue
        # Re-wire deps to skip excluded activities
        original_deps = act.get("depends_on", [])
        new_deps = resolve_deps(original_deps)
        # Remove duplicates and self-refs, keep only included
        new_deps = sorted(set(d for d in new_deps if d in included_ids and d != act["id"]))
        act_copy = dict(act)
        act_copy["depends_on"] = new_deps
        result.append(act_copy)

    return result


def recommend_activities(
    all_activities: list[dict],
    tier: int,
    item_type: str = "feature",
    description: str = "",
    keywords: list[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Recommend which activities to include based on work item context.

    Returns two lists: **required** (always included) and **recommended**
    (suggested based on tier/type/keywords, user can deselect).

    The engine dynamically selects activities by:
    1. Static ``when`` conditions (tier, type)
    2. Keyword matching against the problem description
    3. Activities with ``required: true`` are always included

    Args:
        all_activities: Full list of activity dicts from ``load_phase_activities``.
        tier: Work item scope tier (1-5).
        item_type: Work item type (bug, enhancement, feature, refactor).
        description: Problem statement or work item description for keyword matching.
        keywords: Additional keywords to match against activity descriptions.

    Returns:
        Tuple of (required_activities, recommended_activities).
        Required activities cannot be deselected. Recommended ones are suggestions
        the user can confirm or override.
    """
    if keywords is None:
        keywords = []

    # Extract keywords from description
    desc_lower = description.lower()
    desc_words = set(desc_lower.split())

    required: list[dict] = []
    recommended: list[dict] = []
    excluded: list[dict] = []

    for act in all_activities:
        when = act.get("when")

        # No when clause or required → always required
        if when is None or when.get("required"):
            required.append(act)
            continue

        # Check tier bounds
        min_tier = when.get("min_tier", 1)
        max_tier = when.get("max_tier", 5)
        if tier < min_tier or tier > max_tier:
            # Outside tier range — but check keyword relevance
            if _keyword_match(act, desc_lower, desc_words, keywords):
                recommended.append(act)
            else:
                excluded.append(act)
            continue

        # Check type filter
        allowed_types = when.get("types")
        if allowed_types and item_type not in allowed_types:
            # Wrong type — but check keyword relevance
            if _keyword_match(act, desc_lower, desc_words, keywords):
                recommended.append(act)
            else:
                excluded.append(act)
            continue

        # Passes all static filters → recommended
        recommended.append(act)

    return required, recommended


def _keyword_match(
    activity: dict,
    desc_lower: str,
    desc_words: set[str],
    extra_keywords: list[str],
) -> bool:
    """Check if an activity's name/description matches keywords in the problem description."""
    act_name = activity.get("name", "").lower()
    act_desc = activity.get("description", "").lower()
    act_words = set(act_name.split()) | set(act_desc.split())

    # Check for meaningful word overlap (ignore common words)
    common_words = {"the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "is", "with"}
    meaningful_act_words = act_words - common_words
    meaningful_desc_words = desc_words - common_words

    overlap = meaningful_act_words & meaningful_desc_words
    if len(overlap) >= 2:
        return True

    # Check extra keywords
    for kw in extra_keywords:
        if kw.lower() in act_name or kw.lower() in act_desc:
            return True

    return False


def build_activity_confirmation(
    required: list[dict],
    recommended: list[dict],
    phase: str,
) -> dict:
    """Build an AskUserQuestion payload for confirming activity selection.

    Required activities are shown as pre-selected (informational).
    Recommended activities are shown as a multiSelect checklist.

    Args:
        required: List of required activity dicts (always included).
        recommended: List of recommended activity dicts (user can toggle).
        phase: The phase name.

    Returns:
        AskUserQuestion payload dict.
    """
    # Build options from recommended activities (required are not toggleable)
    options = []
    for act in recommended[:4]:  # Max 4 options
        options.append({
            "label": act["name"],
            "description": act.get("description", "")[:80],
        })

    # If no recommended, just show a confirmation
    if not options:
        options = [
            {
                "label": "Proceed with required activities only",
                "description": f"{len(required)} required activity(ies) for {phase} phase",
            },
            {
                "label": "Add custom activity",
                "description": "Describe an additional activity to include",
            },
        ]

    # Build the question
    req_names = ", ".join(a["name"] for a in required)
    question = (
        f"Activities for {phase.capitalize()} phase. "
        f"Required: {req_names}. "
        f"Which recommended activities should we include?"
        if required
        else f"Which activities should we include for {phase.capitalize()} phase?"
    )

    return {
        "questions": [
            {
                "question": question,
                "header": "Activities",
                "multiSelect": True,
                "options": options,
            }
        ]
    }


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


# ─── Aliases for common naming guesses ────────────────────────────────────────
# Claude often guesses function names. These aliases prevent ImportError.

update_activity_progress = update_activity_status
mark_activity_complete = update_activity_status
update_activity = update_activity_status
complete_activity = update_activity_status
