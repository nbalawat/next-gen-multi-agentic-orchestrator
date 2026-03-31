"""F1 tests for activity manager. Zero LLM calls."""

import json
import pytest
from pathlib import Path

import yaml

from rapids_core.activity_manager import (
    load_phase_activities,
    compute_activity_waves,
    initialize_activity_progress,
    read_activity_progress,
    update_activity_status,
    get_activity_inputs,
    check_phase_gate,
    format_activity_checklist,
)


@pytest.fixture
def activities_dir(tmp_path):
    """Create a temp directory with sample activity YAML files."""
    d = tmp_path / "activities"
    d.mkdir()

    # Research phase with a simple DAG
    research = {
        "phase": "research",
        "activities": [
            {
                "id": "domain-survey",
                "name": "Domain Survey",
                "description": "Explore domain",
                "inputs": [{"name": "project_description", "type": "text", "source": "user"}],
                "outputs": [{"name": "domain-findings", "type": "markdown", "file": "domain-findings.md"}],
                "agent": "rapids-lead",
                "model": "opus",
                "gate": False,
            },
            {
                "id": "constraints",
                "name": "Constraint Mapping",
                "description": "Identify constraints",
                "inputs": [{"name": "project_description", "type": "text", "source": "user"}],
                "outputs": [{"name": "constraints", "type": "markdown", "file": "constraints.md"}],
                "agent": "rapids-lead",
                "model": "opus",
                "gate": False,
            },
            {
                "id": "problem-statement",
                "name": "Problem Statement",
                "description": "Synthesize research",
                "depends_on": ["domain-survey", "constraints"],
                "inputs": [
                    {"name": "domain-findings", "type": "markdown", "from": "domain-survey"},
                    {"name": "constraints", "type": "markdown", "from": "constraints"},
                ],
                "outputs": [{"name": "problem-statement", "type": "markdown", "file": "problem-statement.md"}],
                "agent": "rapids-lead",
                "model": "opus",
                "gate": True,
            },
        ],
    }
    (d / "research.yaml").write_text(yaml.dump(research))

    # Minimal analysis phase
    analysis = {
        "phase": "analysis",
        "activities": [
            {
                "id": "architecture-design",
                "name": "Architecture Design",
                "description": "Design the solution",
                "outputs": [{"name": "solution-design", "file": "solution-design.md"}],
                "gate": True,
            },
        ],
    }
    (d / "analysis.yaml").write_text(yaml.dump(analysis))

    return d


class TestLoadPhaseActivities:
    def test_loads_research_activities(self, activities_dir):
        acts = load_phase_activities("research", activities_dir=activities_dir)
        assert len(acts) == 3
        ids = [a["id"] for a in acts]
        assert "domain-survey" in ids
        assert "problem-statement" in ids

    def test_sets_defaults(self, activities_dir):
        acts = load_phase_activities("analysis", activities_dir=activities_dir)
        act = acts[0]
        assert act["depends_on"] == []
        assert act["source"] == "core"
        assert "agent" in act
        assert "model" in act

    def test_missing_phase_raises(self, activities_dir):
        with pytest.raises(FileNotFoundError):
            load_phase_activities("nonexistent", activities_dir=activities_dir)

    def test_no_plugins(self, activities_dir):
        acts = load_phase_activities("research", activities_dir=activities_dir)
        assert all(a["source"] == "core" for a in acts)


class TestPluginMerge:
    def test_single_plugin_merge(self, activities_dir):
        plugin_acts = {
            "rapids-gcp": [
                {
                    "id": "architecture-review",
                    "name": "GCP Architecture Review",
                    "depends_on": ["domain-survey"],
                    "outputs": [{"name": "gcp-review", "file": "gcp-review.md"}],
                    "gate": True,
                },
            ],
        }
        acts = load_phase_activities("research", activities_dir=activities_dir, plugin_activities=plugin_acts)
        assert len(acts) == 4  # 3 core + 1 plugin
        gcp_act = [a for a in acts if "gcp:" in a["id"]][0]
        assert gcp_act["id"] == "gcp:architecture-review"
        assert gcp_act["source"] == "rapids-gcp"

    def test_two_plugins_merge(self, activities_dir):
        plugin_acts = {
            "rapids-gcp": [
                {"id": "gcp-review", "name": "GCP Review", "depends_on": ["domain-survey"]},
            ],
            "rapids-react": [
                {"id": "ui-plan", "name": "UI Planning", "depends_on": ["domain-survey"]},
            ],
        }
        acts = load_phase_activities("research", activities_dir=activities_dir, plugin_activities=plugin_acts)
        assert len(acts) == 5  # 3 core + 2 plugins
        ids = [a["id"] for a in acts]
        assert "gcp:gcp-review" in ids
        assert "react:ui-plan" in ids

    def test_plugin_ids_prefixed_no_collision(self, activities_dir):
        plugin_acts = {
            "rapids-gcp": [
                {"id": "review", "name": "GCP Review"},
            ],
            "rapids-react": [
                {"id": "review", "name": "React Review"},
            ],
        }
        acts = load_phase_activities("research", activities_dir=activities_dir, plugin_activities=plugin_acts)
        ids = [a["id"] for a in acts]
        assert "gcp:review" in ids
        assert "react:review" in ids
        assert ids.count("gcp:review") == 1
        assert ids.count("react:review") == 1

    def test_plugin_depends_on_core(self, activities_dir):
        plugin_acts = {
            "rapids-gcp": [
                {"id": "gcp-review", "name": "GCP Review", "depends_on": ["domain-survey"]},
            ],
        }
        acts = load_phase_activities("research", activities_dir=activities_dir, plugin_activities=plugin_acts)
        gcp = [a for a in acts if a["id"] == "gcp:gcp-review"][0]
        assert "domain-survey" in gcp["depends_on"]


class TestComputeActivityWaves:
    def test_research_dag(self, activities_dir):
        acts = load_phase_activities("research", activities_dir=activities_dir)
        waves = compute_activity_waves(acts)
        assert len(waves) == 2
        # Wave 1: domain-survey and constraints (no deps)
        assert set(waves[0]) == {"domain-survey", "constraints"}
        # Wave 2: problem-statement (depends on both)
        assert waves[1] == ["problem-statement"]

    def test_single_activity(self, activities_dir):
        acts = load_phase_activities("analysis", activities_dir=activities_dir)
        waves = compute_activity_waves(acts)
        assert len(waves) == 1
        assert waves[0] == ["architecture-design"]

    def test_with_plugin_activities(self, activities_dir):
        plugin_acts = {
            "rapids-gcp": [
                {
                    "id": "gcp-review",
                    "name": "GCP Review",
                    "depends_on": ["domain-survey"],
                },
            ],
        }
        acts = load_phase_activities("research", activities_dir=activities_dir, plugin_activities=plugin_acts)
        waves = compute_activity_waves(acts)
        # Wave 1: domain-survey, constraints (no deps)
        assert "domain-survey" in waves[0]
        assert "constraints" in waves[0]
        # Wave 2: gcp:gcp-review (depends on domain-survey), problem-statement might be here too
        wave2_ids = waves[1]
        assert "gcp:gcp-review" in wave2_ids


class TestActivityProgress:
    def test_initialize_progress(self, activities_dir, tmp_path):
        acts = load_phase_activities("research", activities_dir=activities_dir)
        progress = initialize_activity_progress("research", acts, str(tmp_path))
        assert progress["phase"] == "research"
        assert len(progress["activities"]) == 3
        assert all(a["status"] == "pending" for a in progress["activities"].values())

    def test_progress_file_created(self, activities_dir, tmp_path):
        acts = load_phase_activities("research", activities_dir=activities_dir)
        initialize_activity_progress("research", acts, str(tmp_path))
        assert (tmp_path / "activity-progress-research.json").exists()

    def test_read_progress(self, activities_dir, tmp_path):
        acts = load_phase_activities("research", activities_dir=activities_dir)
        initialize_activity_progress("research", acts, str(tmp_path))
        progress = read_activity_progress(str(tmp_path / "activity-progress-research.json"))
        assert progress["phase"] == "research"

    def test_update_status(self, activities_dir, tmp_path):
        acts = load_phase_activities("research", activities_dir=activities_dir)
        initialize_activity_progress("research", acts, str(tmp_path))
        pf = str(tmp_path / "activity-progress-research.json")

        updated = update_activity_status(pf, "domain-survey", "in_progress")
        assert updated["activities"]["domain-survey"]["status"] == "in_progress"
        assert updated["activities"]["domain-survey"]["started_at"] is not None

    def test_complete_with_outputs(self, activities_dir, tmp_path):
        acts = load_phase_activities("research", activities_dir=activities_dir)
        initialize_activity_progress("research", acts, str(tmp_path))
        pf = str(tmp_path / "activity-progress-research.json")

        updated = update_activity_status(
            pf, "domain-survey", "complete",
            outputs={"domain-findings": "domain-findings.md"},
        )
        assert updated["activities"]["domain-survey"]["status"] == "complete"
        assert updated["activities"]["domain-survey"]["outputs"]["domain-findings"] == "domain-findings.md"

    def test_unknown_activity_raises(self, activities_dir, tmp_path):
        acts = load_phase_activities("research", activities_dir=activities_dir)
        initialize_activity_progress("research", acts, str(tmp_path))
        pf = str(tmp_path / "activity-progress-research.json")

        with pytest.raises(ValueError, match="not found"):
            update_activity_status(pf, "nonexistent", "complete")

    def test_persists_to_file(self, activities_dir, tmp_path):
        acts = load_phase_activities("research", activities_dir=activities_dir)
        initialize_activity_progress("research", acts, str(tmp_path))
        pf = str(tmp_path / "activity-progress-research.json")

        update_activity_status(pf, "domain-survey", "complete")
        reread = read_activity_progress(pf)
        assert reread["activities"]["domain-survey"]["status"] == "complete"


class TestActivityInputResolution:
    def test_resolves_from_completed_activity(self, activities_dir, tmp_path):
        acts = load_phase_activities("research", activities_dir=activities_dir)
        initialize_activity_progress("research", acts, str(tmp_path))
        pf = str(tmp_path / "activity-progress-research.json")

        update_activity_status(pf, "domain-survey", "complete",
                               outputs={"domain-findings": "domain-findings.md"})
        progress = read_activity_progress(pf)

        problem_stmt = [a for a in acts if a["id"] == "problem-statement"][0]
        resolved = get_activity_inputs(problem_stmt, progress, str(tmp_path))
        assert resolved["domain-findings"] == "domain-findings.md"

    def test_unresolved_from_pending_activity(self, activities_dir, tmp_path):
        acts = load_phase_activities("research", activities_dir=activities_dir)
        initialize_activity_progress("research", acts, str(tmp_path))
        progress = read_activity_progress(str(tmp_path / "activity-progress-research.json"))

        problem_stmt = [a for a in acts if a["id"] == "problem-statement"][0]
        resolved = get_activity_inputs(problem_stmt, progress, str(tmp_path))
        assert resolved["domain-findings"] is None

    def test_user_source_input(self, activities_dir, tmp_path):
        acts = load_phase_activities("research", activities_dir=activities_dir)
        progress = {"activities": {}}
        domain = [a for a in acts if a["id"] == "domain-survey"][0]
        resolved = get_activity_inputs(domain, progress, str(tmp_path))
        assert resolved["project_description"] == "(user-provided)"


class TestPhaseGate:
    def test_gate_passes_when_all_complete(self, activities_dir, tmp_path):
        acts = load_phase_activities("research", activities_dir=activities_dir)
        initialize_activity_progress("research", acts, str(tmp_path))
        pf = str(tmp_path / "activity-progress-research.json")

        # problem-statement is the only gate activity
        update_activity_status(pf, "problem-statement", "complete")
        assert check_phase_gate(pf) is True

    def test_gate_fails_when_gate_activity_pending(self, activities_dir, tmp_path):
        acts = load_phase_activities("research", activities_dir=activities_dir)
        initialize_activity_progress("research", acts, str(tmp_path))
        pf = str(tmp_path / "activity-progress-research.json")

        # Complete non-gate activities but not the gate one
        update_activity_status(pf, "domain-survey", "complete")
        update_activity_status(pf, "constraints", "complete")
        assert check_phase_gate(pf) is False

    def test_gate_ignores_non_gate_activities(self, activities_dir, tmp_path):
        acts = load_phase_activities("research", activities_dir=activities_dir)
        initialize_activity_progress("research", acts, str(tmp_path))
        pf = str(tmp_path / "activity-progress-research.json")

        # Only complete the gate activity, non-gate still pending
        update_activity_status(pf, "problem-statement", "complete")
        # domain-survey and constraints are NOT gate, so this should pass
        assert check_phase_gate(pf) is True

    def test_plugin_gate_activity(self, activities_dir, tmp_path):
        plugin_acts = {
            "rapids-gcp": [
                {"id": "gcp-review", "name": "GCP Review", "gate": True},
            ],
        }
        acts = load_phase_activities("research", activities_dir=activities_dir, plugin_activities=plugin_acts)
        initialize_activity_progress("research", acts, str(tmp_path))
        pf = str(tmp_path / "activity-progress-research.json")

        # Core gate passes but plugin gate doesn't
        update_activity_status(pf, "problem-statement", "complete")
        assert check_phase_gate(pf) is False

        # Now complete plugin gate
        update_activity_status(pf, "gcp:gcp-review", "complete")
        assert check_phase_gate(pf) is True


class TestFormatActivityChecklist:
    def test_empty_activities(self):
        result = format_activity_checklist([])
        assert "No activities" in result

    def test_pending_activities_show_circle(self, activities_dir):
        acts = load_phase_activities("research", activities_dir=activities_dir)
        result = format_activity_checklist(acts)
        assert "○" in result

    def test_complete_shows_checkmark(self, activities_dir, tmp_path):
        acts = load_phase_activities("research", activities_dir=activities_dir)
        initialize_activity_progress("research", acts, str(tmp_path))
        pf = str(tmp_path / "activity-progress-research.json")
        update_activity_status(pf, "domain-survey", "complete")
        progress = read_activity_progress(pf)

        result = format_activity_checklist(acts, progress)
        assert "✓" in result

    def test_in_progress_shows_arrow(self, activities_dir, tmp_path):
        acts = load_phase_activities("research", activities_dir=activities_dir)
        initialize_activity_progress("research", acts, str(tmp_path))
        pf = str(tmp_path / "activity-progress-research.json")
        update_activity_status(pf, "domain-survey", "in_progress")
        progress = read_activity_progress(pf)

        result = format_activity_checklist(acts, progress)
        assert "→" in result

    def test_shows_gate_marker(self, activities_dir):
        acts = load_phase_activities("research", activities_dir=activities_dir)
        result = format_activity_checklist(acts)
        assert "(gate)" in result

    def test_shows_plugin_source(self, activities_dir):
        plugin_acts = {
            "rapids-gcp": [
                {"id": "gcp-review", "name": "GCP Review"},
            ],
        }
        acts = load_phase_activities("research", activities_dir=activities_dir, plugin_activities=plugin_acts)
        result = format_activity_checklist(acts)
        assert "[rapids-gcp]" in result

    def test_shows_dependencies(self, activities_dir):
        acts = load_phase_activities("research", activities_dir=activities_dir)
        result = format_activity_checklist(acts)
        assert "Depends:" in result


class TestLoadRealActivityFiles:
    """Test loading the actual YAML files from rapids-core/activities/."""

    @pytest.fixture
    def real_activities_dir(self):
        d = Path(__file__).parent.parent.parent / "rapids-core" / "activities"
        if not d.exists():
            pytest.skip("rapids-core/activities/ not found")
        return d

    @pytest.mark.parametrize("phase", ["research", "analysis", "plan", "implement", "deploy", "sustain"])
    def test_all_phases_load(self, real_activities_dir, phase):
        acts = load_phase_activities(phase, activities_dir=real_activities_dir)
        assert len(acts) >= 1
        for act in acts:
            assert "id" in act
            assert "name" in act

    @pytest.mark.parametrize("phase", ["research", "analysis", "plan", "implement", "deploy", "sustain"])
    def test_all_phases_compute_waves(self, real_activities_dir, phase):
        acts = load_phase_activities(phase, activities_dir=real_activities_dir)
        waves = compute_activity_waves(acts)
        assert len(waves) >= 1

    @pytest.mark.parametrize("phase", ["research", "analysis", "plan", "implement", "deploy", "sustain"])
    def test_all_phases_have_at_least_one_gate(self, real_activities_dir, phase):
        acts = load_phase_activities(phase, activities_dir=real_activities_dir)
        gates = [a for a in acts if a.get("gate")]
        assert len(gates) >= 1, f"Phase '{phase}' has no gate activities"
