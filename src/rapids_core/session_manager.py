"""Session Manager: cross-session context persistence for individuals and teams.

Tracks session history, auto-generates summaries from timeline events,
and supports team handoffs with context packaging.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _sessions_dir(project_path: str) -> Path:
    """Get the sessions directory for a project."""
    return Path(project_path) / ".rapids" / "sessions"


def _session_index_path(project_path: str) -> Path:
    return _sessions_dir(project_path) / "session-index.json"


def _load_index(project_path: str) -> list[dict]:
    idx_path = _session_index_path(project_path)
    if idx_path.exists():
        return json.loads(idx_path.read_text())
    return []


def _save_index(project_path: str, index: list[dict]) -> None:
    idx_path = _session_index_path(project_path)
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    idx_path.write_text(json.dumps(index, indent=2) + "\n")


def start_session(
    user: str,
    project_path: str,
    session_id: str | None = None,
) -> str:
    """Start a new session and record it in the index.

    Args:
        user: Username or identifier.
        project_path: Absolute path to the project.
        session_id: Optional explicit session ID. Generated if not provided.

    Returns:
        The session ID.
    """
    if session_id is None:
        session_id = f"S{len(_load_index(project_path)) + 1:03d}"

    now = datetime.now(timezone.utc).isoformat()

    # Load current project state for context
    rapids_json_path = Path(project_path) / ".rapids" / "rapids.json"
    current_phase = "unknown"
    active_work_items: list[str] = []
    if rapids_json_path.exists():
        config = json.loads(rapids_json_path.read_text())
        current_phase = config.get("current", {}).get("phase", "unknown")
        for wi in config.get("work_items", []):
            if wi.get("status") == "active":
                active_work_items.append(wi["id"])

    session = {
        "session_id": session_id,
        "user": user,
        "started_at": now,
        "ended_at": None,
        "phase_on_entry": current_phase,
        "work_items_on_entry": active_work_items,
        "status": "active",
    }

    # Save session file
    sessions_dir = _sessions_dir(project_path)
    sessions_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    session_file = sessions_dir / f"{session_id}-{user}-{date_str}.json"
    session_file.write_text(json.dumps(session, indent=2) + "\n")

    # Update index
    index = _load_index(project_path)
    index.append({
        "session_id": session_id,
        "user": user,
        "started_at": now,
        "file": session_file.name,
        "status": "active",
    })
    _save_index(project_path, index)

    return session_id


def end_session(
    session_id: str,
    project_path: str,
    handoff_notes: str = "",
) -> dict:
    """End a session, generating a summary from timeline events.

    Args:
        session_id: The session to end.
        project_path: Path to the project.
        handoff_notes: Optional notes for the next person picking up this project.

    Returns:
        The finalized session summary dict.
    """
    now = datetime.now(timezone.utc).isoformat()
    sessions_dir = _sessions_dir(project_path)

    # Find and update session file
    session_data = None
    session_file = None
    for f in sessions_dir.glob(f"{session_id}-*.json"):
        session_data = json.loads(f.read_text())
        session_file = f
        break

    if session_data is None:
        raise ValueError(f"Session {session_id} not found")

    # Read timeline events that occurred during this session
    started_at = session_data["started_at"]
    timeline_events = _get_timeline_events_since(project_path, started_at)

    # Generate summary
    summary = summarize_session(timeline_events)

    # Load current state
    rapids_json_path = Path(project_path) / ".rapids" / "rapids.json"
    current_phase = "unknown"
    work_items_touched: list[str] = []
    if rapids_json_path.exists():
        config = json.loads(rapids_json_path.read_text())
        current_phase = config.get("current", {}).get("phase", "unknown")
        for wi in config.get("work_items", []):
            work_items_touched.append(wi["id"])

    session_data.update({
        "ended_at": now,
        "status": "complete",
        "phase_on_exit": current_phase,
        "work_items_touched": work_items_touched,
        "events_count": len(timeline_events),
        "context_summary": summary,
        "handoff_notes": handoff_notes,
    })

    # Save updated session
    session_file.write_text(json.dumps(session_data, indent=2) + "\n")

    # Update index
    index = _load_index(project_path)
    for entry in index:
        if entry["session_id"] == session_id:
            entry["status"] = "complete"
            entry["ended_at"] = now
    _save_index(project_path, index)

    return session_data


def summarize_session(timeline_events: list[dict]) -> str:
    """Auto-generate a session summary from timeline events.

    Args:
        timeline_events: List of timeline event dicts.

    Returns:
        Human-readable summary string.
    """
    if not timeline_events:
        return "No significant activity during this session."

    event_counts: dict[str, int] = {}
    phases_visited: set[str] = set()
    artifacts_created: list[str] = []
    tools_used: set[str] = set()

    for event in timeline_events:
        etype = event.get("event", "unknown")
        event_counts[etype] = event_counts.get(etype, 0) + 1
        phase = event.get("phase", "")
        if phase:
            phases_visited.add(phase)

        details = event.get("details", {})
        if etype in ("artifact_created", "artifact_modified"):
            artifacts_created.append(details.get("path", "unknown"))
        if "tool" in details:
            tools_used.add(details["tool"])

    parts = []
    parts.append(f"Session had {len(timeline_events)} event(s)")

    if phases_visited:
        parts.append(f"across phase(s): {', '.join(sorted(phases_visited))}")

    if artifacts_created:
        parts.append(f". Artifacts created/modified: {', '.join(artifacts_created[:5])}")
        if len(artifacts_created) > 5:
            parts.append(f" (+{len(artifacts_created) - 5} more)")

    event_summary = ", ".join(f"{count} {etype}" for etype, count in sorted(event_counts.items()))
    parts.append(f". Events: {event_summary}.")

    return "".join(parts)


def list_sessions(
    project_path: str,
    user: str | None = None,
) -> list[dict]:
    """List session history for a project.

    Args:
        project_path: Path to the project.
        user: If provided, filter to this user's sessions only.

    Returns:
        List of session index entries.
    """
    index = _load_index(project_path)
    if user:
        return [s for s in index if s.get("user") == user]
    return index


def get_session_context(session_id: str, project_path: str) -> dict | None:
    """Load a prior session's full context for handoff.

    Args:
        session_id: The session ID to load.
        project_path: Path to the project.

    Returns:
        The session summary dict, or None if not found.
    """
    sessions_dir = _sessions_dir(project_path)
    for f in sessions_dir.glob(f"{session_id}-*.json"):
        return json.loads(f.read_text())
    return None


def create_team_handoff(
    from_session_id: str,
    to_user: str,
    project_path: str,
    notes: str = "",
) -> dict:
    """Package context from one session for handoff to another team member.

    Args:
        from_session_id: The session to hand off from.
        to_user: The user receiving the handoff.
        project_path: Path to the project.
        notes: Additional handoff notes.

    Returns:
        Handoff dict with context, notes, and next steps.
    """
    source = get_session_context(from_session_id, project_path)
    if source is None:
        raise ValueError(f"Session {from_session_id} not found")

    # Load current project state
    rapids_json_path = Path(project_path) / ".rapids" / "rapids.json"
    active_work_items = []
    current_phase = "unknown"
    if rapids_json_path.exists():
        config = json.loads(rapids_json_path.read_text())
        current_phase = config.get("current", {}).get("phase", "unknown")
        for wi in config.get("work_items", []):
            if wi.get("status") == "active":
                active_work_items.append({
                    "id": wi["id"],
                    "title": wi.get("title", ""),
                    "phase": wi.get("current_phase", ""),
                })

    # Load accumulated context
    acc_path = Path(project_path) / ".rapids" / "context" / "accumulated.json"
    accumulated = json.loads(acc_path.read_text()) if acc_path.exists() else {}

    return {
        "handoff_from": source.get("user", "unknown"),
        "handoff_to": to_user,
        "from_session": from_session_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_state": {
            "current_phase": current_phase,
            "active_work_items": active_work_items,
        },
        "prior_session_summary": source.get("context_summary", ""),
        "prior_handoff_notes": source.get("handoff_notes", ""),
        "new_notes": notes,
        "key_decisions": accumulated.get("key_decisions", []),
        "constraints": accumulated.get("constraints", []),
    }


def format_session_history(sessions: list[dict]) -> str:
    """Format session history as an ASCII table.

    Args:
        sessions: List of session index entries.

    Returns:
        Formatted table string.
    """
    if not sessions:
        return "  No sessions recorded.\n"

    lines = []
    lines.append(f"  {'ID':<8} {'USER':<15} {'STARTED':<22} {'STATUS':<10}")
    lines.append("  " + "─" * 58)

    for s in sessions:
        started = s.get("started_at", "?")[:19]
        lines.append(
            f"  {s.get('session_id', '?'):<8} "
            f"{s.get('user', '?'):<15} "
            f"{started:<22} "
            f"{s.get('status', '?'):<10}"
        )

    return "\n".join(lines) + "\n"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_timeline_events_since(project_path: str, since_ts: str) -> list[dict]:
    """Read timeline events that occurred after the given timestamp."""
    timeline_path = Path(project_path) / ".rapids" / "audit" / "timeline.jsonl"
    if not timeline_path.exists():
        return []

    events = []
    for line in timeline_path.read_text().strip().split("\n"):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            if entry.get("ts", "") >= since_ts:
                events.append(entry)
        except json.JSONDecodeError:
            continue

    return events
