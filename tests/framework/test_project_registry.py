"""F1 tests for project registry. Zero LLM calls."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from rapids_core.project_registry import (
    register_project,
    update_project_phase,
    deactivate_project,
    list_projects,
    get_project,
    format_project_table,
    register_workspace,
    list_workspaces,
    get_workspace,
    get_workspace_projects,
    infer_workspace,
    _ensure_registry,
    _save_registry,
)


@pytest.fixture
def tmp_registry(tmp_path):
    """Redirect registry to a temp directory."""
    registry_dir = tmp_path / ".rapids"
    registry_file = registry_dir / "projects.json"
    with patch("rapids_core.project_registry.REGISTRY_DIR", registry_dir), \
         patch("rapids_core.project_registry.REGISTRY_FILE", registry_file):
        yield registry_file


class TestProjectRegistry:
    def test_ensure_registry_creates_file(self, tmp_registry):
        assert not tmp_registry.exists()
        registry = _ensure_registry()
        assert tmp_registry.exists()
        assert registry == {"workspaces": [], "projects": []}

    def test_register_new_project(self, tmp_registry):
        entry = register_project(
            name="test-project",
            path="/tmp/test-project",
            tier=3,
            phase="analysis",
            plugins=["rapids-gcp"],
        )
        assert entry["name"] == "test-project"
        assert entry["path"] == "/tmp/test-project"
        assert entry["tier"] == 3
        assert entry["phase"] == "analysis"
        assert entry["plugins"] == ["rapids-gcp"]
        assert entry["status"] == "active"
        assert "created_at" in entry
        assert "updated_at" in entry

    def test_register_updates_existing_by_path(self, tmp_registry):
        register_project("proj-v1", "/tmp/proj", tier=2, phase="plan")
        entry = register_project("proj-v2", "/tmp/proj", tier=3, phase="analysis")
        assert entry["name"] == "proj-v2"
        assert entry["tier"] == 3
        # Should still be one entry, not two
        projects = list_projects(active_only=False)
        assert len(projects) == 1

    def test_register_multiple_projects(self, tmp_registry):
        register_project("proj-a", "/tmp/a", tier=1, phase="implement")
        register_project("proj-b", "/tmp/b", tier=4, phase="research")
        projects = list_projects()
        assert len(projects) == 2

    def test_update_project_phase(self, tmp_registry):
        register_project("proj", "/tmp/proj", tier=3, phase="analysis")
        result = update_project_phase("/tmp/proj", "plan")
        assert result is not None
        assert result["phase"] == "plan"

    def test_update_phase_not_found(self, tmp_registry):
        result = update_project_phase("/tmp/nonexistent", "plan")
        assert result is None

    def test_deactivate_project(self, tmp_registry):
        register_project("proj", "/tmp/proj", tier=2, phase="plan")
        result = deactivate_project("/tmp/proj")
        assert result is not None
        assert result["status"] == "inactive"

    def test_deactivate_not_found(self, tmp_registry):
        result = deactivate_project("/tmp/nonexistent")
        assert result is None

    def test_list_active_only(self, tmp_registry):
        register_project("active", "/tmp/active", tier=1, phase="implement")
        register_project("inactive", "/tmp/inactive", tier=2, phase="plan")
        deactivate_project("/tmp/inactive")
        active = list_projects(active_only=True)
        assert len(active) == 1
        assert active[0]["name"] == "active"

    def test_list_all(self, tmp_registry):
        register_project("a", "/tmp/a", tier=1, phase="implement")
        register_project("b", "/tmp/b", tier=2, phase="plan")
        deactivate_project("/tmp/b")
        all_projs = list_projects(active_only=False)
        assert len(all_projs) == 2

    def test_get_project(self, tmp_registry):
        register_project("proj", "/tmp/proj", tier=3, phase="analysis")
        result = get_project("/tmp/proj")
        assert result is not None
        assert result["name"] == "proj"

    def test_get_project_not_found(self, tmp_registry):
        result = get_project("/tmp/nonexistent")
        assert result is None


class TestWorkspace:
    def test_register_workspace(self, tmp_registry):
        ws = register_workspace("my-ws", "/tmp/my-workspace")
        assert ws["name"] == "my-ws"
        assert ws["path"] == "/tmp/my-workspace"
        assert "created_at" in ws
        assert ws["projects"] == []

    def test_register_workspace_idempotent(self, tmp_registry):
        register_workspace("ws-v1", "/tmp/ws")
        ws = register_workspace("ws-v2", "/tmp/ws")
        assert ws["name"] == "ws-v2"
        assert len(list_workspaces()) == 1

    def test_list_workspaces(self, tmp_registry):
        register_workspace("ws-a", "/tmp/a")
        register_workspace("ws-b", "/tmp/b")
        assert len(list_workspaces()) == 2

    def test_get_workspace(self, tmp_registry):
        register_workspace("ws", "/tmp/ws")
        result = get_workspace("/tmp/ws")
        assert result is not None
        assert result["name"] == "ws"

    def test_get_workspace_not_found(self, tmp_registry):
        assert get_workspace("/tmp/nonexistent") is None

    def test_project_auto_associates_with_workspace(self, tmp_registry):
        register_workspace("ws", "/tmp/ws")
        entry = register_project("proj", "/tmp/ws/proj", tier=2, phase="plan")
        assert entry["workspace"] == "/tmp/ws"

    def test_workspace_projects_list(self, tmp_registry):
        register_workspace("ws", "/tmp/ws")
        register_project("p1", "/tmp/ws/p1", tier=1, phase="implement")
        register_project("p2", "/tmp/ws/p2", tier=2, phase="plan")
        register_project("standalone", "/tmp/other", tier=3, phase="analysis")
        ws_projs = get_workspace_projects("/tmp/ws")
        assert len(ws_projs) == 2
        assert all(p["workspace"] == "/tmp/ws" for p in ws_projs)

    def test_infer_workspace(self, tmp_registry):
        register_workspace("ws", "/tmp/ws")
        assert infer_workspace("/tmp/ws/proj-a") == "/tmp/ws"

    def test_infer_workspace_none(self, tmp_registry):
        register_workspace("ws", "/tmp/ws")
        assert infer_workspace("/tmp/other/proj") is None

    def test_list_projects_by_workspace(self, tmp_registry):
        register_workspace("ws", "/tmp/ws")
        register_project("p1", "/tmp/ws/p1", tier=1, phase="implement")
        register_project("p2", "/tmp/other", tier=2, phase="plan")
        projs = list_projects(workspace="/tmp/ws")
        assert len(projs) == 1
        assert projs[0]["name"] == "p1"

    def test_deactivate_updates_workspace(self, tmp_registry):
        register_workspace("ws", "/tmp/ws")
        register_project("p1", "/tmp/ws/p1", tier=1, phase="implement")
        deactivate_project("/tmp/ws/p1")
        ws = get_workspace("/tmp/ws")
        assert "p1" not in ws["projects"]

    def test_explicit_workspace_overrides_infer(self, tmp_registry):
        register_workspace("ws-a", "/tmp/a")
        register_workspace("ws-b", "/tmp/b")
        entry = register_project("p", "/tmp/a/p", tier=1, phase="implement", workspace="/tmp/b")
        assert entry["workspace"] == "/tmp/b"


class TestFormatProjectTable:
    def test_empty_projects(self):
        result = format_project_table([])
        assert "No active" in result

    def test_formats_projects(self):
        projects = [
            {
                "name": "my-project",
                "path": "/tmp/my-project",
                "tier": 3,
                "phase": "implement",
                "status": "active",
            },
        ]
        result = format_project_table(projects)
        assert "my-project" in result
        assert "T3" in result
        assert "implement" in result
        assert "●" in result

    def test_inactive_shows_empty_circle(self):
        projects = [
            {
                "name": "old-proj",
                "path": "/tmp/old",
                "tier": 1,
                "phase": "implement",
                "status": "inactive",
            },
        ]
        result = format_project_table(projects)
        assert "○" in result

    def test_workspace_grouping(self):
        projects = [
            {
                "name": "p1",
                "path": "/tmp/ws/p1",
                "workspace": "/tmp/ws",
                "tier": 1,
                "phase": "implement",
                "status": "active",
            },
            {
                "name": "p2",
                "path": "/tmp/ws/p2",
                "workspace": "/tmp/ws",
                "tier": 2,
                "phase": "plan",
                "status": "active",
            },
        ]
        result = format_project_table(projects)
        assert "Workspace: /tmp/ws" in result
        assert "p1" in result
        assert "p2" in result
