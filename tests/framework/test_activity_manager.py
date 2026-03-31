"""F1 tests for activity manager. Zero LLM calls."""

import json
import pytest
from pathlib import Path

import yaml

from rapids_core.activity_manager import (
    load_phase_activities,
    select_activities,
    recommend_activities,
    build_activity_confirmation,
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


class TestSelectActivities:
    """Test activity filtering based on tier, type, and when conditions."""

    def _make_activities(self):
        return [
            {"id": "a1", "name": "Always", "depends_on": []},
            {"id": "a2", "name": "Required", "when": {"required": True}, "depends_on": []},
            {"id": "a3", "name": "Tier 3+", "when": {"min_tier": 3}, "depends_on": []},
            {"id": "a4", "name": "Tier 4+", "when": {"min_tier": 4}, "depends_on": ["a3"]},
            {"id": "a5", "name": "Feature only", "when": {"types": ["feature"]}, "depends_on": ["a1"]},
            {"id": "a6", "name": "Tier 1-2", "when": {"max_tier": 2}, "depends_on": []},
        ]

    def test_no_when_always_included(self):
        acts = self._make_activities()
        selected = select_activities(acts, tier=1, item_type="bug")
        ids = [a["id"] for a in selected]
        assert "a1" in ids

    def test_required_always_included(self):
        acts = self._make_activities()
        selected = select_activities(acts, tier=1, item_type="bug")
        ids = [a["id"] for a in selected]
        assert "a2" in ids

    def test_min_tier_filters(self):
        acts = self._make_activities()
        # Tier 1: a3 (min_tier=3) should be excluded
        selected = select_activities(acts, tier=1)
        ids = [a["id"] for a in selected]
        assert "a3" not in ids
        # Tier 3: a3 should be included
        selected = select_activities(acts, tier=3)
        ids = [a["id"] for a in selected]
        assert "a3" in ids

    def test_max_tier_filters(self):
        acts = self._make_activities()
        # Tier 1: a6 (max_tier=2) should be included
        selected = select_activities(acts, tier=1)
        ids = [a["id"] for a in selected]
        assert "a6" in ids
        # Tier 3: a6 should be excluded
        selected = select_activities(acts, tier=3)
        ids = [a["id"] for a in selected]
        assert "a6" not in ids

    def test_type_filters(self):
        acts = self._make_activities()
        # Feature type: a5 included
        selected = select_activities(acts, tier=1, item_type="feature")
        ids = [a["id"] for a in selected]
        assert "a5" in ids
        # Bug type: a5 excluded
        selected = select_activities(acts, tier=1, item_type="bug")
        ids = [a["id"] for a in selected]
        assert "a5" not in ids

    def test_dependency_rewiring(self):
        """When a4 depends on a3 and a3 is pruned, a4's deps should skip a3."""
        acts = self._make_activities()
        # Tier 5: both a3 and a4 included
        selected = select_activities(acts, tier=5)
        a4 = [a for a in selected if a["id"] == "a4"][0]
        assert "a3" in a4["depends_on"]

    def test_dependency_rewiring_on_prune(self):
        """Chain: c depends on b, b depends on a. Prune b. c should depend on a."""
        acts = [
            {"id": "a", "name": "Base", "depends_on": []},
            {"id": "b", "name": "Middle", "when": {"min_tier": 5}, "depends_on": ["a"]},
            {"id": "c", "name": "Top", "when": {"required": True}, "depends_on": ["b"]},
        ]
        selected = select_activities(acts, tier=3)  # b excluded
        ids = [a["id"] for a in selected]
        assert "b" not in ids
        c = [a for a in selected if a["id"] == "c"][0]
        assert "a" in c["depends_on"]

    def test_tier_1_bug_minimal_activities(self):
        """A Tier 1 bug fix should get minimal activities."""
        acts = self._make_activities()
        selected = select_activities(acts, tier=1, item_type="bug")
        ids = [a["id"] for a in selected]
        # Only: a1 (no when), a2 (required), a6 (max_tier=2)
        assert set(ids) == {"a1", "a2", "a6"}

    def test_tier_5_feature_all_applicable(self):
        """A Tier 5 feature should get all activities except max_tier=2."""
        acts = self._make_activities()
        selected = select_activities(acts, tier=5, item_type="feature")
        ids = [a["id"] for a in selected]
        assert "a1" in ids
        assert "a2" in ids
        assert "a3" in ids
        assert "a4" in ids
        assert "a5" in ids
        assert "a6" not in ids  # max_tier=2, excluded at tier 5

    def test_selected_activities_form_valid_dag(self):
        """After filtering, the remaining activities should form a valid DAG."""
        acts = self._make_activities()
        for tier in range(1, 6):
            selected = select_activities(acts, tier=tier)
            # All depends_on should reference included activities
            included = {a["id"] for a in selected}
            for act in selected:
                for dep in act["depends_on"]:
                    assert dep in included, f"Tier {tier}: {act['id']} depends on pruned {dep}"

    def test_real_research_yaml_tier_1(self):
        """Tier 1 bug fix in research phase gets only required activities."""
        real_dir = Path(__file__).parent.parent.parent / "rapids-core" / "activities"
        if not real_dir.exists():
            pytest.skip("rapids-core/activities/ not found")
        acts = load_phase_activities("research", activities_dir=real_dir)
        selected = select_activities(acts, tier=1, item_type="bug")
        ids = [a["id"] for a in selected]
        # Only problem-statement is required
        assert "problem-statement" in ids
        # domain-survey (min_tier=3) excluded
        assert "domain-survey" not in ids


class TestRecommendActivities:
    """Test dynamic activity recommendation based on tier, type, and description."""

    def _make_activities(self):
        return [
            {"id": "a-required", "name": "Core Setup", "when": {"required": True}, "depends_on": [],
             "description": "Essential setup"},
            {"id": "a-tier3", "name": "Architecture Review", "when": {"min_tier": 3}, "depends_on": [],
             "description": "Review architecture design patterns"},
            {"id": "a-tier5", "name": "Compliance Audit", "when": {"min_tier": 5}, "depends_on": [],
             "description": "Security compliance and audit trail verification"},
            {"id": "a-feature", "name": "Feature Planning", "when": {"types": ["feature"]}, "depends_on": [],
             "description": "Plan feature implementation strategy"},
            {"id": "a-always", "name": "Testing", "depends_on": [],
             "description": "Run automated testing suite"},
        ]

    def test_required_always_in_required_list(self):
        req, rec = recommend_activities(self._make_activities(), tier=1, item_type="bug")
        req_ids = [a["id"] for a in req]
        assert "a-required" in req_ids

    def test_no_when_always_in_required(self):
        req, rec = recommend_activities(self._make_activities(), tier=1, item_type="bug")
        req_ids = [a["id"] for a in req]
        assert "a-always" in req_ids

    def test_tier_match_goes_to_recommended(self):
        req, rec = recommend_activities(self._make_activities(), tier=3, item_type="feature")
        rec_ids = [a["id"] for a in rec]
        assert "a-tier3" in rec_ids

    def test_tier_mismatch_excluded_unless_keywords(self):
        req, rec = recommend_activities(self._make_activities(), tier=1, item_type="bug")
        all_ids = [a["id"] for a in req + rec]
        assert "a-tier3" not in all_ids

    def test_keyword_match_rescues_excluded_activity(self):
        """If description mentions architecture, a-tier3 gets recommended even at tier 1."""
        req, rec = recommend_activities(
            self._make_activities(), tier=1, item_type="bug",
            description="Fix architecture design patterns in the auth module",
        )
        rec_ids = [a["id"] for a in rec]
        assert "a-tier3" in rec_ids

    def test_extra_keywords_match(self):
        req, rec = recommend_activities(
            self._make_activities(), tier=1, item_type="bug",
            keywords=["compliance"],
        )
        rec_ids = [a["id"] for a in rec]
        assert "a-tier5" in rec_ids

    def test_type_mismatch_excluded_unless_keywords(self):
        req, rec = recommend_activities(
            self._make_activities(), tier=3, item_type="bug",
        )
        all_ids = [a["id"] for a in req + rec]
        assert "a-feature" not in all_ids

    def test_tier_1_bug_minimal(self):
        req, rec = recommend_activities(self._make_activities(), tier=1, item_type="bug")
        assert len(req) == 2  # a-required + a-always
        assert len(rec) == 0

    def test_tier_5_feature_maximal(self):
        req, rec = recommend_activities(self._make_activities(), tier=5, item_type="feature")
        total = len(req) + len(rec)
        assert total == 5  # All activities


class TestBuildActivityConfirmation:
    def test_produces_valid_payload(self):
        required = [{"id": "r1", "name": "Required One"}]
        recommended = [
            {"id": "a1", "name": "Optional One", "description": "First optional"},
            {"id": "a2", "name": "Optional Two", "description": "Second optional"},
        ]
        payload = build_activity_confirmation(required, recommended, "research")
        assert "questions" in payload
        q = payload["questions"][0]
        assert q["multiSelect"] is True
        assert len(q["options"]) == 2

    def test_mentions_required_in_question(self):
        required = [{"id": "r1", "name": "Problem Statement"}]
        recommended = [{"id": "a1", "name": "Domain Survey", "description": "Explore domain"}]
        payload = build_activity_confirmation(required, recommended, "research")
        q = payload["questions"][0]["question"]
        assert "Problem Statement" in q

    def test_empty_recommended_still_valid(self):
        required = [{"id": "r1", "name": "Only Required"}]
        payload = build_activity_confirmation(required, [], "plan")
        assert "questions" in payload
        assert len(payload["questions"][0]["options"]) >= 2

    def test_max_four_options(self):
        recommended = [
            {"id": f"a{i}", "name": f"Act {i}", "description": f"Desc {i}"}
            for i in range(6)
        ]
        payload = build_activity_confirmation([], recommended, "analysis")
        assert len(payload["questions"][0]["options"]) <= 4


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
