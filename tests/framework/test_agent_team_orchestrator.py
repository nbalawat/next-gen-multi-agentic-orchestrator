"""F1 tests for agent team orchestrator. Zero LLM calls."""

import pytest

from rapids_core.agent_team_orchestrator import (
    parse_agent_definition,
    resolve_generator_agent,
    detect_coordination_needs,
    create_agent_team_plan,
)


TERRAFORM_AGENT_MD = """---
name: terraform-engineer
model: sonnet
effort: medium
phase: implement
role: coder
isolation: worktree
tools:
  - read
  - write
  - edit
  - bash
description: Terraform engineer for infrastructure-as-code
---

# Terraform Engineer Agent

You are a Terraform engineer...
"""

REACT_AGENT_MD = """---
name: react-developer
model: sonnet
effort: medium
phase: implement
role: coder
isolation: worktree
description: React frontend developer
---

# React Developer Agent
"""

ARCHITECT_AGENT_MD = """---
name: gcp-architect
model: opus
effort: high
phase: analysis
role: architect
description: GCP architecture design
---

# GCP Architect Agent
"""


def _make_spec(fid: str = "F001", plugin: str = "gcp", name: str = "Test Feature") -> str:
    return f"""<feature id="{fid}" version="1.0" priority="high" depends_on="" plugin="{plugin}">
    <n>{name}</n>
    <description>Description of {fid}</description>
    <acceptance_criteria>
        <criterion>Criterion for {fid}</criterion>
    </acceptance_criteria>
    <estimated_complexity>M</estimated_complexity>
</feature>"""


class TestParseAgentDefinition:
    def test_parses_yaml_frontmatter(self):
        result = parse_agent_definition(TERRAFORM_AGENT_MD)
        assert result["name"] == "terraform-engineer"
        assert result["model"] == "sonnet"

    def test_extracts_name_model_role(self):
        result = parse_agent_definition(TERRAFORM_AGENT_MD)
        assert result["role"] == "coder"
        assert result["phase"] == "implement"
        assert result["isolation"] == "worktree"

    def test_extracts_tools_list(self):
        result = parse_agent_definition(TERRAFORM_AGENT_MD)
        assert "read" in result["tools"]
        assert "bash" in result["tools"]

    def test_handles_no_frontmatter(self):
        result = parse_agent_definition("# Just a heading\n\nSome content")
        assert result == {}

    def test_handles_empty_string(self):
        result = parse_agent_definition("")
        assert result == {}

    def test_handles_malformed_yaml(self):
        result = parse_agent_definition("---\n: invalid: yaml: [\n---\n")
        assert result == {}


class TestResolveGeneratorAgent:
    def test_matches_plugin_specific_coder(self):
        agents = [
            parse_agent_definition(TERRAFORM_AGENT_MD),
            parse_agent_definition(REACT_AGENT_MD),
        ]
        name, model = resolve_generator_agent("F001", "gcp", agents)
        assert name == "terraform-engineer"

    def test_matches_react_plugin(self):
        agents = [
            parse_agent_definition(TERRAFORM_AGENT_MD),
            parse_agent_definition(REACT_AGENT_MD),
        ]
        name, model = resolve_generator_agent("F001", "react", agents)
        assert name == "react-developer"

    def test_falls_back_to_rapids_lead(self):
        name, model = resolve_generator_agent("F001", "unknown", [])
        assert name == "rapids-lead"
        assert model == "opus"

    def test_prefers_implement_phase_agents(self):
        agents = [
            parse_agent_definition(ARCHITECT_AGENT_MD),  # analysis phase, not implement
            parse_agent_definition(TERRAFORM_AGENT_MD),   # implement phase
        ]
        name, model = resolve_generator_agent("F001", "gcp", agents)
        assert name == "terraform-engineer"

    def test_falls_back_to_first_coder_if_no_plugin_match(self):
        agents = [parse_agent_definition(TERRAFORM_AGENT_MD)]
        name, model = resolve_generator_agent("F001", "unknown-plugin", agents)
        assert name == "terraform-engineer"

    def test_empty_plugin_falls_back(self):
        agents = [parse_agent_definition(TERRAFORM_AGENT_MD)]
        name, model = resolve_generator_agent("F001", "", agents)
        assert name == "terraform-engineer"


class TestDetectCoordinationNeeds:
    def test_multi_plugin_produces_note(self):
        notes = detect_coordination_needs(
            ["F001", "F002"],
            {"features": ["F001", "F002"], "dependencies": {}},
            {"F001": "rapids-gcp", "F002": "rapids-react"},
        )
        assert any("Multi-plugin" in n for n in notes)

    def test_single_plugin_no_multi_plugin_note(self):
        notes = detect_coordination_needs(
            ["F001", "F002"],
            {"features": ["F001", "F002"], "dependencies": {}},
            {"F001": "rapids-gcp", "F002": "rapids-gcp"},
        )
        assert not any("Multi-plugin" in n for n in notes)

    def test_intra_wave_deps_produces_note(self):
        notes = detect_coordination_needs(
            ["F001", "F002"],
            {"features": ["F001", "F002"], "dependencies": {"F002": ["F001"]}},
            {"F001": "default", "F002": "default"},
        )
        assert any("Intra-wave" in n for n in notes)

    def test_no_intra_wave_deps_no_note(self):
        notes = detect_coordination_needs(
            ["F001", "F002"],
            {"features": ["F001", "F002", "F003"], "dependencies": {"F002": ["F003"]}},
            {"F001": "default", "F002": "default"},
        )
        assert not any("Intra-wave" in n for n in notes)

    def test_shared_plugin_file_conflict_note(self):
        notes = detect_coordination_needs(
            ["F001", "F002"],
            {"features": ["F001", "F002"], "dependencies": {}},
            {"F001": "rapids-gcp", "F002": "rapids-gcp"},
        )
        assert any("file conflicts" in n for n in notes)


class TestCreateAgentTeamPlan:
    def test_single_feature_plan(self):
        plan = create_agent_team_plan(
            wave_number=1,
            wave_features=["F001"],
            feature_specs={"F001": _make_spec("F001")},
        )
        assert plan["wave_number"] == 1
        assert plan["total_features"] == 1
        assert len(plan["assignments"]) == 1

    def test_multi_feature_plan(self):
        plan = create_agent_team_plan(
            wave_number=2,
            wave_features=["F001", "F002"],
            feature_specs={
                "F001": _make_spec("F001"),
                "F002": _make_spec("F002"),
            },
        )
        assert plan["total_features"] == 2

    def test_assignments_have_worktree_branches(self):
        plan = create_agent_team_plan(
            wave_number=1,
            wave_features=["F001"],
            feature_specs={"F001": _make_spec("F001")},
            project_id="my-proj",
        )
        assert plan["assignments"][0]["worktree_branch"] == "rapids/my-proj/F001"

    def test_evaluator_model_higher_than_generator(self):
        agents = [parse_agent_definition(TERRAFORM_AGENT_MD)]  # model: sonnet
        plan = create_agent_team_plan(
            wave_number=1,
            wave_features=["F001"],
            feature_specs={"F001": _make_spec("F001", plugin="gcp")},
            feature_plugins={"F001": "gcp"},
            available_agents=agents,
        )
        assignment = plan["assignments"][0]
        assert assignment["generator_model"] == "sonnet"
        assert assignment["evaluator_model"] == "opus"  # one tier up

    def test_max_retries_propagated(self):
        plan = create_agent_team_plan(
            wave_number=1,
            wave_features=["F001"],
            feature_specs={"F001": _make_spec("F001")},
            max_retries=5,
        )
        assert plan["assignments"][0]["max_retries"] == 5

    def test_coordination_notes_included(self):
        plan = create_agent_team_plan(
            wave_number=1,
            wave_features=["F001", "F002"],
            feature_specs={
                "F001": _make_spec("F001"),
                "F002": _make_spec("F002"),
            },
            feature_plugins={"F001": "rapids-gcp", "F002": "rapids-react"},
            dependency_graph={
                "features": ["F001", "F002"],
                "dependencies": {},
            },
        )
        assert len(plan["coordination_notes"]) > 0

    def test_execution_mode_always_agent_teams(self):
        plan = create_agent_team_plan(
            wave_number=1,
            wave_features=["F001"],
            feature_specs={"F001": _make_spec("F001")},
        )
        assert plan["execution_mode"] == "agent_teams"

    def test_empty_wave_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            create_agent_team_plan(
                wave_number=1,
                wave_features=[],
                feature_specs={},
            )

    def test_missing_feature_spec_raises(self):
        with pytest.raises(ValueError, match="Missing feature spec"):
            create_agent_team_plan(
                wave_number=1,
                wave_features=["F001"],
                feature_specs={},
            )

    def test_lead_agent_is_rapids_lead(self):
        plan = create_agent_team_plan(
            wave_number=1,
            wave_features=["F001"],
            feature_specs={"F001": _make_spec("F001")},
        )
        assert plan["lead_agent"] == "rapids-lead"

    def test_confirmation_required(self):
        plan = create_agent_team_plan(
            wave_number=1,
            wave_features=["F001"],
            feature_specs={"F001": _make_spec("F001")},
        )
        assert plan["confirmation_required"] is True

    def test_features_sorted_in_assignments(self):
        plan = create_agent_team_plan(
            wave_number=1,
            wave_features=["F003", "F001", "F002"],
            feature_specs={
                "F001": _make_spec("F001"),
                "F002": _make_spec("F002"),
                "F003": _make_spec("F003"),
            },
        )
        ids = [a["feature_id"] for a in plan["assignments"]]
        assert ids == ["F001", "F002", "F003"]
