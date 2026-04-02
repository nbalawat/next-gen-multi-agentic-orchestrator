"""Timeline logger: writes audit events to timeline.jsonl.

This module provides a direct API for logging timeline events,
independent of hook firing. Skills and scripts call these functions
directly to ensure events are always recorded.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def log_event(
    rapids_dir: str,
    event: str,
    phase: str = "",
    details: dict | None = None,
    feature: str = "",
) -> dict:
    """Append an event to the timeline audit log.

    Args:
        rapids_dir: Path to the ``.rapids/`` directory.
        event: Event type (e.g., ``session_start``, ``phase_transition``,
               ``artifact_created``, ``feature_started``, ``feature_completed``).
        phase: Current phase name.
        details: Additional event-specific details.
        feature: Optional feature ID.

    Returns:
        The logged entry dict.
    """
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "phase": phase,
    }
    if feature:
        entry["feature"] = feature
    if details:
        entry["details"] = details

    timeline_file = Path(rapids_dir) / "audit" / "timeline.jsonl"
    timeline_file.parent.mkdir(parents=True, exist_ok=True)
    with open(timeline_file, "a") as f:
        f.write(json.dumps(entry) + "\n")

    return entry


def log_phase_transition(
    rapids_dir: str,
    from_phase: str,
    to_phase: str,
    work_item_id: str = "",
) -> dict:
    """Log a phase transition event."""
    return log_event(
        rapids_dir,
        event="phase_transition",
        phase=to_phase,
        details={
            "from_phase": from_phase,
            "to_phase": to_phase,
            "work_item": work_item_id,
        },
    )


def log_feature_started(
    rapids_dir: str,
    feature_id: str,
    phase: str = "implement",
) -> dict:
    """Log a feature implementation starting."""
    return log_event(
        rapids_dir,
        event="feature_started",
        phase=phase,
        feature=feature_id,
    )


def log_feature_completed(
    rapids_dir: str,
    feature_id: str,
    verdict: str = "pass",
    phase: str = "implement",
) -> dict:
    """Log a feature implementation completing."""
    return log_event(
        rapids_dir,
        event="feature_completed",
        phase=phase,
        feature=feature_id,
        details={"verdict": verdict},
    )


def log_artifact_created(
    rapids_dir: str,
    artifact_path: str,
    phase: str,
    activity: str = "",
) -> dict:
    """Log an artifact being created or modified."""
    return log_event(
        rapids_dir,
        event="artifact_created",
        phase=phase,
        details={
            "path": artifact_path,
            "activity": activity,
        },
    )


def log_work_item_created(
    rapids_dir: str,
    work_item_id: str,
    title: str,
    item_type: str,
    tier: int,
) -> dict:
    """Log a new work item being created."""
    return log_event(
        rapids_dir,
        event="work_item_created",
        details={
            "work_item": work_item_id,
            "title": title,
            "type": item_type,
            "tier": tier,
        },
    )


def log_session_event(
    rapids_dir: str,
    event_type: str,
    session_id: str = "",
    user: str = "",
) -> dict:
    """Log a session start or end event."""
    return log_event(
        rapids_dir,
        event=event_type,
        details={
            "session_id": session_id,
            "user": user,
        },
    )


def read_timeline(rapids_dir: str, since: str | None = None) -> list[dict]:
    """Read timeline events, optionally filtering by timestamp.

    Args:
        rapids_dir: Path to the ``.rapids/`` directory.
        since: If provided, only return events with ts >= this value.

    Returns:
        List of event dicts.
    """
    timeline_file = Path(rapids_dir) / "audit" / "timeline.jsonl"
    if not timeline_file.exists():
        return []

    events = []
    for line in timeline_file.read_text().strip().split("\n"):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            if since and entry.get("ts", "") < since:
                continue
            events.append(entry)
        except json.JSONDecodeError:
            continue

    return events
