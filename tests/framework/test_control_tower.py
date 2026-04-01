"""F1 tests for Control Tower. Zero LLM calls."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from rapids_core.control_tower import (
    project_health,
    compliance_check,
    generate_report,
    alert_check,
    format_dashboard,
    export_report,
)


@pytest.fixture
def project_dir(tmp_path):
    """Create a project directory with .rapids/ structure."""
    proj = tmp_path / "my-project"
    proj.mkdir()
    rapids = proj / ".rapids"
    rapids.mkdir()
    (rapids / "audit").mkdir()
    (rapids / "phases").mkdir()
    (rapids / "phases" / "implement").mkdir()
    (rapids / "context").mkdir()
    (rapids / "audit" / "timeline.jsonl").write_text(
        '{"ts":"2026-03-31T12:00:00Z","event":"session_start","phase":"implement","details":{}}\n'
    )
    (rapids / "audit" / "cost.jsonl").write_text("")
    (rapids / "rapids.json").write_text(json.dumps({
        "project": {"id": "my-project"},
        "scope": {"default_tier": 3},
        "work_items": [
            {"id": "WI-001", "title": "Build API", "type": "feature", "tier": 3,
             "phases": ["analysis", "plan", "implement", "deploy"],
             "current_phase": "implement", "status": "active"},
        ],
        "active_work_item": "WI-001",
        "current": {"phase": "implement"},
        "plugins": [],
    }))
    return proj


@pytest.fixture
def multi_project_setup(tmp_path):
    """Create multiple projects in a workspace for report testing."""
    ws = tmp_path / "workspace"
    ws.mkdir()

    projects = []
    for name, tier, phase, status in [
        ("proj-a", 3, "implement", "active"),
        ("proj-b", 1, "implement", "active"),
        ("proj-c", 4, "deploy", "active"),
    ]:
        proj = ws / name
        proj.mkdir()
        rapids = proj / ".rapids"
        rapids.mkdir()
        (rapids / "audit").mkdir()
        (rapids / "phases").mkdir()
        (rapids / "context").mkdir()
        (rapids / "audit" / "timeline.jsonl").write_text(
            f'{{"ts":"2026-03-31T12:00:00Z","event":"session_start","phase":"{phase}","details":{{}}}}\n'
        )
        (rapids / "audit" / "cost.jsonl").write_text("")
        (rapids / "rapids.json").write_text(json.dumps({
            "project": {"id": name},
            "scope": {"default_tier": tier},
            "work_items": [
                {"id": "WI-001", "title": f"Work on {name}", "type": "feature",
                 "tier": tier, "phases": ["implement"], "current_phase": phase,
                 "status": status},
            ],
            "active_work_item": "WI-001",
            "current": {"phase": phase},
            "plugins": [],
        }))
        projects.append({"name": name, "path": str(proj), "tier": tier,
                         "phase": phase, "status": "active", "workspace": str(ws)})

    return ws, projects


class TestProjectHealth:
    def test_healthy_project(self, project_dir):
        health = project_health(str(project_dir))
        assert health["status"] == "green"
        assert health["active_work_items"] == 1
        assert health["last_activity"] is not None

    def test_no_rapids_dir(self, tmp_path):
        health = project_health(str(tmp_path / "nonexistent"))
        assert health["status"] == "red"
        assert "No .rapids/rapids.json" in health["reasons"][0]

    def test_failed_evaluator_verdict_is_yellow(self, project_dir):
        impl_dir = project_dir / ".rapids" / "phases" / "implement"
        (impl_dir / "feature-progress-F001.json").write_text(json.dumps({
            "feature_id": "F001", "status": "in_progress",
            "evaluator_verdict": "fail", "retry_count": 2,
            "acceptance_criteria": [],
        }))
        health = project_health(str(project_dir))
        assert health["status"] == "yellow"
        assert any("failed evaluation" in r for r in health["reasons"])

    def test_cost_tracked(self, project_dir):
        cost_file = project_dir / ".rapids" / "audit" / "cost.jsonl"
        cost_file.write_text(
            '{"ts":"2026-03-31T12:00:00Z","phase":"implement","feature":"F001",'
            '"model":"sonnet","input_tokens":1000,"output_tokens":500,"cost_usd":0.15}\n'
        )
        health = project_health(str(project_dir))
        assert health["cost_total"] == pytest.approx(0.15)

    def test_no_work_items_is_red(self, project_dir):
        config = json.loads((project_dir / ".rapids" / "rapids.json").read_text())
        config["work_items"] = []
        (project_dir / ".rapids" / "rapids.json").write_text(json.dumps(config))
        health = project_health(str(project_dir))
        assert health["status"] == "red"


class TestComplianceCheck:
    def test_compliant_project(self, project_dir):
        result = compliance_check(str(project_dir))
        assert result["compliant"] is True
        assert result["audit_files_present"] is True

    def test_missing_audit_files(self, project_dir):
        (project_dir / ".rapids" / "audit" / "timeline.jsonl").unlink()
        result = compliance_check(str(project_dir))
        assert result["compliant"] is False
        assert "Missing audit files" in result["issues"][0]

    def test_counts_gates(self, project_dir):
        phase_dir = project_dir / ".rapids" / "phases" / "implement"
        (phase_dir / "activity-progress-implement.json").write_text(json.dumps({
            "phase": "implement",
            "activities": {
                "wave-execution": {"status": "complete", "gate": True},
                "code-review": {"status": "pending", "gate": False},
                "integration-testing": {"status": "pending", "gate": True},
            },
        }))
        result = compliance_check(str(project_dir))
        assert result["gates_passed"] == 1
        assert result["gates_pending"] == 1


class TestGenerateReport:
    def test_report_structure(self, multi_project_setup):
        ws, projects = multi_project_setup
        with patch("rapids_core.control_tower.list_workspaces") as mock_ws, \
             patch("rapids_core.control_tower.list_projects") as mock_projs:
            mock_ws.return_value = [{"name": "test-ws", "path": str(ws), "projects": []}]
            mock_projs.return_value = projects
            report = generate_report()

        assert "generated_at" in report
        assert "workspaces" in report
        assert "global_stats" in report
        assert "compliance" in report
        assert report["global_stats"]["total_projects"] == 3

    def test_report_includes_all_projects(self, multi_project_setup):
        ws, projects = multi_project_setup
        with patch("rapids_core.control_tower.list_workspaces") as mock_ws, \
             patch("rapids_core.control_tower.list_projects") as mock_projs:
            mock_ws.return_value = [{"name": "test-ws", "path": str(ws), "projects": []}]
            mock_projs.return_value = projects
            report = generate_report()

        ws_report = report["workspaces"][0]
        assert len(ws_report["projects"]) == 3

    def test_empty_registry(self):
        with patch("rapids_core.control_tower.list_workspaces") as mock_ws, \
             patch("rapids_core.control_tower.list_projects") as mock_projs:
            mock_ws.return_value = []
            mock_projs.return_value = []
            report = generate_report()

        assert report["global_stats"]["total_projects"] == 0


class TestAlertCheck:
    def test_no_alerts_for_healthy(self):
        report = {
            "workspaces": [{
                "name": "ws",
                "projects": [{"name": "p", "health": "green", "health_reasons": [],
                              "gates_pending": 0}],
            }],
            "compliance": {"all_compliant": True},
        }
        assert alert_check(report) == []

    def test_red_project_alert(self):
        report = {
            "workspaces": [{
                "name": "ws",
                "projects": [{"name": "broken", "health": "red",
                              "health_reasons": ["No work items"], "gates_pending": 0}],
            }],
            "compliance": {"all_compliant": True},
        }
        alerts = alert_check(report)
        assert len(alerts) == 1
        assert "[RED]" in alerts[0]

    def test_yellow_project_alert(self):
        report = {
            "workspaces": [{
                "name": "ws",
                "projects": [{"name": "stalled", "health": "yellow",
                              "health_reasons": ["Feature F001 failed"], "gates_pending": 0}],
            }],
            "compliance": {"all_compliant": True},
        }
        alerts = alert_check(report)
        assert any("[WARN]" in a for a in alerts)

    def test_many_pending_gates_alert(self):
        report = {
            "workspaces": [{
                "name": "ws",
                "projects": [{"name": "p", "health": "green", "health_reasons": [],
                              "gates_pending": 5}],
            }],
            "compliance": {"all_compliant": True},
        }
        alerts = alert_check(report)
        assert any("[GATE]" in a for a in alerts)

    def test_compliance_alert(self):
        report = {
            "workspaces": [{"name": "ws", "projects": []}],
            "compliance": {"all_compliant": False},
        }
        alerts = alert_check(report)
        assert any("[COMPLIANCE]" in a for a in alerts)


class TestFormatDashboard:
    def test_contains_header(self):
        report = {
            "workspaces": [], "global_stats": {
                "total_projects": 0, "total_cost": 0, "active_work_items": 0,
                "completed_work_items": 0,
            }, "compliance": {"all_compliant": True},
        }
        result = format_dashboard(report)
        assert "C O N T R O L   T O W E R" in result

    def test_shows_project(self, multi_project_setup):
        ws, projects = multi_project_setup
        report = {
            "generated_at": "now",
            "workspaces": [{
                "name": "test-ws",
                "projects": [{
                    "name": "proj-a", "tier": 3, "health": "green",
                    "health_reasons": [], "work_items": {"active": 1, "complete": 0},
                    "cost": {"total": 1.50}, "current_phases": ["implement"],
                    "gates_passed": 2, "gates_pending": 1, "last_activity": "now",
                }],
            }],
            "global_stats": {"total_projects": 1, "total_cost": 1.50,
                             "active_work_items": 1, "completed_work_items": 0},
            "compliance": {"all_compliant": True},
        }
        result = format_dashboard(report)
        assert "proj-a" in result
        assert "$1.50" in result

    def test_shows_alerts(self):
        report = {
            "workspaces": [{
                "name": "ws",
                "projects": [{"name": "bad", "health": "red", "tier": 1,
                              "health_reasons": ["Broken"], "work_items": {"active": 0, "complete": 0},
                              "cost": {"total": 0}, "current_phases": [],
                              "gates_passed": 0, "gates_pending": 0, "last_activity": None}],
            }],
            "global_stats": {"total_projects": 1, "total_cost": 0,
                             "active_work_items": 0, "completed_work_items": 0},
            "compliance": {"all_compliant": True},
        }
        result = format_dashboard(report)
        assert "ALERTS" in result


class TestExportReport:
    def test_json_export(self):
        report = {"generated_at": "now", "workspaces": [], "global_stats": {}, "compliance": {}}
        result = export_report(report, fmt="json")
        parsed = json.loads(result)
        assert parsed["generated_at"] == "now"

    def test_markdown_export(self):
        report = {
            "generated_at": "2026-03-31",
            "workspaces": [{
                "name": "ws",
                "projects": [{"name": "p", "tier": 3, "health": "green",
                              "work_items": {"active": 1}, "cost": {"total": 5.0},
                              "gates_passed": 3, "gates_pending": 0}],
            }],
            "global_stats": {"total_projects": 1, "total_cost": 5.0,
                             "active_work_items": 1, "completed_work_items": 0},
            "compliance": {"all_compliant": True},
        }
        result = export_report(report, fmt="md")
        assert "# RAPIDS Control Tower Report" in result
        assert "| p |" in result
