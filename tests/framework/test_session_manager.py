"""F1 tests for Session Manager. Zero LLM calls."""

import json
import pytest
from pathlib import Path

from rapids_core.session_manager import (
    start_session,
    end_session,
    summarize_session,
    list_sessions,
    get_session_context,
    create_team_handoff,
    format_session_history,
)


@pytest.fixture
def project_dir(tmp_path):
    """Create a project with .rapids/ structure for session testing."""
    proj = tmp_path / "my-project"
    proj.mkdir()
    rapids = proj / ".rapids"
    rapids.mkdir()
    (rapids / "audit").mkdir()
    (rapids / "context").mkdir()
    (rapids / "phases").mkdir()
    (rapids / "audit" / "timeline.jsonl").write_text(
        '{"ts":"2026-03-31T10:00:00Z","event":"session_start","phase":"implement","details":{}}\n'
        '{"ts":"2026-03-31T11:00:00Z","event":"artifact_created","phase":"implement","details":{"path":"feature.py","tool":"Write"}}\n'
        '{"ts":"2026-03-31T12:00:00Z","event":"tool_use","phase":"implement","details":{"tool":"Bash"}}\n'
    )
    (rapids / "audit" / "cost.jsonl").write_text("")
    (rapids / "rapids.json").write_text(json.dumps({
        "project": {"id": "my-project"},
        "work_items": [
            {"id": "WI-001", "title": "Build API", "type": "feature",
             "tier": 3, "current_phase": "implement", "status": "active"},
        ],
        "active_work_item": "WI-001",
        "current": {"phase": "implement"},
    }))
    (rapids / "context" / "accumulated.json").write_text(json.dumps({
        "key_decisions": ["Use PostgreSQL", "REST API"],
        "constraints": ["Must support IE11"],
    }))
    return proj


class TestStartSession:
    def test_returns_session_id(self, project_dir):
        sid = start_session("naveen", str(project_dir))
        assert sid.startswith("S")

    def test_creates_session_file(self, project_dir):
        sid = start_session("naveen", str(project_dir))
        sessions_dir = project_dir / ".rapids" / "sessions"
        files = list(sessions_dir.glob(f"{sid}-*.json"))
        assert len(files) == 1

    def test_session_file_content(self, project_dir):
        sid = start_session("naveen", str(project_dir))
        sessions_dir = project_dir / ".rapids" / "sessions"
        f = list(sessions_dir.glob(f"{sid}-*.json"))[0]
        data = json.loads(f.read_text())
        assert data["user"] == "naveen"
        assert data["status"] == "active"
        assert data["phase_on_entry"] == "implement"

    def test_updates_index(self, project_dir):
        start_session("naveen", str(project_dir))
        idx = json.loads((project_dir / ".rapids" / "sessions" / "session-index.json").read_text())
        assert len(idx) == 1
        assert idx[0]["user"] == "naveen"

    def test_explicit_session_id(self, project_dir):
        sid = start_session("naveen", str(project_dir), session_id="S999")
        assert sid == "S999"

    def test_multiple_sessions(self, project_dir):
        s1 = start_session("naveen", str(project_dir))
        s2 = start_session("alice", str(project_dir))
        assert s1 != s2
        idx = json.loads((project_dir / ".rapids" / "sessions" / "session-index.json").read_text())
        assert len(idx) == 2


class TestEndSession:
    def test_ends_session(self, project_dir):
        sid = start_session("naveen", str(project_dir))
        result = end_session(sid, str(project_dir))
        assert result["status"] == "complete"
        assert result["ended_at"] is not None

    def test_generates_summary(self, project_dir):
        sid = start_session("naveen", str(project_dir))
        result = end_session(sid, str(project_dir))
        assert result["context_summary"] != ""
        assert "event" in result["context_summary"].lower() or "session" in result["context_summary"].lower()

    def test_captures_handoff_notes(self, project_dir):
        sid = start_session("naveen", str(project_dir))
        result = end_session(sid, str(project_dir), handoff_notes="F002 blocked on frontend")
        assert result["handoff_notes"] == "F002 blocked on frontend"

    def test_updates_index(self, project_dir):
        sid = start_session("naveen", str(project_dir))
        end_session(sid, str(project_dir))
        idx = json.loads((project_dir / ".rapids" / "sessions" / "session-index.json").read_text())
        assert idx[0]["status"] == "complete"

    def test_unknown_session_raises(self, project_dir):
        with pytest.raises(ValueError, match="not found"):
            end_session("S999", str(project_dir))


class TestSummarizeSession:
    def test_empty_events(self):
        result = summarize_session([])
        assert "No significant activity" in result

    def test_counts_events(self):
        events = [
            {"event": "tool_use", "phase": "implement", "details": {"tool": "Write"}},
            {"event": "tool_use", "phase": "implement", "details": {"tool": "Bash"}},
            {"event": "artifact_created", "phase": "implement", "details": {"path": "main.py"}},
        ]
        result = summarize_session(events)
        assert "3 event" in result

    def test_mentions_phases(self):
        events = [
            {"event": "tool_use", "phase": "implement", "details": {}},
            {"event": "tool_use", "phase": "deploy", "details": {}},
        ]
        result = summarize_session(events)
        assert "implement" in result
        assert "deploy" in result

    def test_mentions_artifacts(self):
        events = [
            {"event": "artifact_created", "phase": "analysis", "details": {"path": "solution-design.md"}},
        ]
        result = summarize_session(events)
        assert "solution-design.md" in result


class TestListSessions:
    def test_empty(self, project_dir):
        assert list_sessions(str(project_dir)) == []

    def test_lists_all(self, project_dir):
        start_session("naveen", str(project_dir))
        start_session("alice", str(project_dir))
        sessions = list_sessions(str(project_dir))
        assert len(sessions) == 2

    def test_filter_by_user(self, project_dir):
        start_session("naveen", str(project_dir))
        start_session("alice", str(project_dir))
        sessions = list_sessions(str(project_dir), user="naveen")
        assert len(sessions) == 1
        assert sessions[0]["user"] == "naveen"


class TestGetSessionContext:
    def test_gets_active_session(self, project_dir):
        sid = start_session("naveen", str(project_dir))
        ctx = get_session_context(sid, str(project_dir))
        assert ctx is not None
        assert ctx["user"] == "naveen"

    def test_gets_completed_session(self, project_dir):
        sid = start_session("naveen", str(project_dir))
        end_session(sid, str(project_dir), handoff_notes="Check F002")
        ctx = get_session_context(sid, str(project_dir))
        assert ctx["status"] == "complete"
        assert ctx["handoff_notes"] == "Check F002"

    def test_unknown_session(self, project_dir):
        assert get_session_context("S999", str(project_dir)) is None


class TestCreateTeamHandoff:
    def test_creates_handoff(self, project_dir):
        sid = start_session("naveen", str(project_dir))
        end_session(sid, str(project_dir), handoff_notes="Check auth module")
        handoff = create_team_handoff(sid, "alice", str(project_dir), notes="Focus on F002")
        assert handoff["handoff_from"] == "naveen"
        assert handoff["handoff_to"] == "alice"
        assert handoff["new_notes"] == "Focus on F002"

    def test_includes_project_state(self, project_dir):
        sid = start_session("naveen", str(project_dir))
        end_session(sid, str(project_dir))
        handoff = create_team_handoff(sid, "alice", str(project_dir))
        assert handoff["project_state"]["current_phase"] == "implement"
        assert len(handoff["project_state"]["active_work_items"]) >= 1

    def test_includes_accumulated_context(self, project_dir):
        sid = start_session("naveen", str(project_dir))
        end_session(sid, str(project_dir))
        handoff = create_team_handoff(sid, "alice", str(project_dir))
        assert "Use PostgreSQL" in handoff["key_decisions"]
        assert "Must support IE11" in handoff["constraints"]

    def test_includes_prior_summary(self, project_dir):
        sid = start_session("naveen", str(project_dir))
        end_session(sid, str(project_dir))
        handoff = create_team_handoff(sid, "alice", str(project_dir))
        assert handoff["prior_session_summary"] != ""

    def test_unknown_session_raises(self, project_dir):
        with pytest.raises(ValueError, match="not found"):
            create_team_handoff("S999", "alice", str(project_dir))


class TestFormatSessionHistory:
    def test_empty(self):
        result = format_session_history([])
        assert "No sessions" in result

    def test_shows_sessions(self):
        sessions = [
            {"session_id": "S001", "user": "naveen", "started_at": "2026-03-31T10:00:00Z", "status": "complete"},
            {"session_id": "S002", "user": "alice", "started_at": "2026-03-31T14:00:00Z", "status": "active"},
        ]
        result = format_session_history(sessions)
        assert "S001" in result
        assert "naveen" in result
        assert "S002" in result
        assert "alice" in result
