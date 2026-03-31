"""F1 tests for ASCII art banners. Zero LLM calls."""

import pytest

from rapids_core.ascii_art import (
    phase_banner,
    welcome_banner,
    transition_banner,
    activity_banner,
    PHASE_LABELS,
    ALL_PHASE_KEYS,
    _wrap_text,
)


class TestPhaseBanner:
    def test_contains_phase_label(self):
        result = phase_banner("implement")
        assert "IMPLEMENTATION" in result

    def test_contains_rapids_title(self):
        result = phase_banner("implement")
        assert "R A P I D S" in result

    def test_shows_project_name(self):
        result = phase_banner("plan", project_name="my-project")
        assert "my-project" in result

    def test_shows_tier(self):
        result = phase_banner("plan", tier=3)
        assert "3" in result
        assert "Feature" in result

    def test_shows_activity(self):
        result = phase_banner("implement", activity="Wave 1 — Feature F001")
        assert "CURRENT ACTIVITY" in result
        assert "Wave 1" in result
        assert "F001" in result

    def test_current_phase_highlighted(self):
        result = phase_banner("plan", phases_in_scope=["analysis", "plan", "implement", "deploy"])
        # Current phase should have the block marker
        assert "▶" in result

    def test_completed_phases_have_checkmark(self):
        result = phase_banner("implement", phases_in_scope=["analysis", "plan", "implement", "deploy"])
        # analysis and plan should be completed (before implement)
        assert "✓" in result

    def test_future_phases_have_circle(self):
        result = phase_banner("plan", phases_in_scope=["analysis", "plan", "implement", "deploy"])
        # implement and deploy should be upcoming
        assert "○" in result

    def test_out_of_scope_phases_have_dot(self):
        result = phase_banner("implement", phases_in_scope=["implement"])
        # research, analysis, plan, deploy, sustain should be out of scope
        assert "·" in result

    def test_all_tiers_have_labels(self):
        for tier in range(1, 6):
            result = phase_banner("implement", tier=tier)
            assert str(tier) in result

    def test_all_phases_render(self):
        for phase in ALL_PHASE_KEYS:
            result = phase_banner(phase)
            _, label, _ = PHASE_LABELS[phase]
            assert label in result


class TestWelcomeBanner:
    def test_contains_logo(self):
        result = welcome_banner()
        assert "██████╗" in result

    def test_contains_framework_label(self):
        result = welcome_banner()
        assert "Orchestration Framework" in result

    def test_no_projects_or_workspaces_message(self):
        result = welcome_banner(projects=[], workspaces=[])
        assert "No workspaces or projects" in result

    def test_shows_flat_projects_without_workspaces(self):
        projects = [
            {
                "name": "test-proj",
                "path": "/tmp/test",
                "tier": 2,
                "phase": "plan",
                "status": "active",
            },
        ]
        result = welcome_banner(projects)
        assert "test-proj" in result
        assert "T2" in result
        assert "plan" in result

    def test_shows_workspace_with_projects(self):
        workspaces = [
            {"name": "my-workspace", "path": "/tmp/ws", "projects": ["proj-a", "proj-b"]},
        ]
        projects = [
            {"name": "proj-a", "path": "/tmp/ws/a", "workspace": "/tmp/ws", "tier": 3, "phase": "implement", "status": "active"},
            {"name": "proj-b", "path": "/tmp/ws/b", "workspace": "/tmp/ws", "tier": 1, "phase": "implement", "status": "active"},
        ]
        result = welcome_banner(projects, workspaces)
        assert "my-workspace" in result
        assert "proj-a" in result
        assert "proj-b" in result

    def test_shows_empty_workspace(self):
        workspaces = [
            {"name": "empty-ws", "path": "/tmp/empty", "projects": []},
        ]
        result = welcome_banner(projects=[], workspaces=workspaces)
        assert "empty-ws" in result
        assert "no projects yet" in result

    def test_shows_standalone_projects_separately(self):
        workspaces = [
            {"name": "ws", "path": "/tmp/ws", "projects": ["proj-a"]},
        ]
        projects = [
            {"name": "proj-a", "path": "/tmp/ws/a", "workspace": "/tmp/ws", "tier": 2, "phase": "plan", "status": "active"},
            {"name": "standalone", "path": "/tmp/other", "tier": 1, "phase": "implement", "status": "active"},
        ]
        result = welcome_banner(projects, workspaces)
        assert "Standalone" in result
        assert "standalone" in result

    def test_prompts_for_workspace(self):
        result = welcome_banner()
        assert "workspace" in result.lower()


class TestTransitionBanner:
    def test_shows_from_and_to(self):
        result = transition_banner("analysis", "plan")
        assert "ARCHITECTURE" in result
        assert "PLANNING" in result

    def test_shows_arrow(self):
        result = transition_banner("plan", "implement")
        assert "▶" in result

    def test_shows_project_name(self):
        result = transition_banner("plan", "implement", project_name="my-proj")
        assert "my-proj" in result

    def test_all_transitions(self):
        for i in range(len(ALL_PHASE_KEYS) - 1):
            from_p = ALL_PHASE_KEYS[i]
            to_p = ALL_PHASE_KEYS[i + 1]
            result = transition_banner(from_p, to_p)
            assert "PHASE TRANSITION" in result


class TestActivityBanner:
    def test_shows_phase(self):
        result = activity_banner("implement", "Working on F001")
        assert "IMPLEMENTATION" in result

    def test_shows_activity_text(self):
        result = activity_banner("deploy", "Running smoke tests")
        assert "Running smoke tests" in result

    def test_compact_format(self):
        result = activity_banner("plan", "Computing waves")
        assert "R A P I D S" in result
        # Should use simple box characters
        assert "┌" in result
        assert "└" in result


class TestWrapText:
    def test_short_text(self):
        assert _wrap_text("hello", 80) == ["hello"]

    def test_wraps_long_text(self):
        text = "this is a long sentence that should be wrapped at the boundary"
        lines = _wrap_text(text, 30)
        assert len(lines) > 1
        for line in lines:
            assert len(line) <= 30

    def test_empty_text(self):
        assert _wrap_text("", 80) == [""]

    def test_single_long_word(self):
        # A single word longer than width should remain on one line
        result = _wrap_text("superlongword", 5)
        assert result == ["superlongword"]
