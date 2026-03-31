"""F1 tests for batch dispatcher. Zero LLM calls."""

import pytest

from rapids_core.batch_dispatcher import (
    build_feature_prompt,
    create_batch_dispatch_plan,
    format_batch_command,
)


def _make_spec(
    fid: str = "F001",
    depends_on: str = "",
    plugin: str = "gcp",
    name: str = "Test Feature",
) -> str:
    return f"""<feature id="{fid}" version="1.0" priority="high" depends_on="{depends_on}" plugin="{plugin}">
    <n>{name}</n>
    <description>Description of {fid}</description>
    <acceptance_criteria>
        <criterion>First criterion for {fid}</criterion>
        <criterion>Second criterion for {fid}</criterion>
    </acceptance_criteria>
    <estimated_complexity>M</estimated_complexity>
</feature>"""


class TestBuildFeaturePrompt:
    def test_includes_feature_name_and_description(self):
        prompt = build_feature_prompt(_make_spec(name="Payment Widget"))
        assert "Payment Widget" in prompt
        assert "Description of F001" in prompt

    def test_includes_all_acceptance_criteria(self):
        prompt = build_feature_prompt(_make_spec())
        assert "First criterion for F001" in prompt
        assert "Second criterion for F001" in prompt

    def test_includes_accumulated_context(self):
        context = {
            "key_decisions": ["Use PostgreSQL", "REST over gRPC"],
            "constraints": ["Must support IE11"],
        }
        prompt = build_feature_prompt(_make_spec(), accumulated_context=context)
        assert "Use PostgreSQL" in prompt
        assert "REST over gRPC" in prompt
        assert "Must support IE11" in prompt

    def test_includes_evaluator_template(self):
        template = "Run all tests\nCheck coverage > 80%"
        prompt = build_feature_prompt(_make_spec(), evaluator_template=template)
        assert "Run all tests" in prompt
        assert "Check coverage > 80%" in prompt

    def test_handles_missing_context_gracefully(self):
        prompt = build_feature_prompt(_make_spec())
        assert "Project Context" not in prompt

    def test_handles_empty_evaluator_template(self):
        prompt = build_feature_prompt(_make_spec(), evaluator_template="")
        assert "Self-Verification" not in prompt

    def test_includes_generator_pattern_instructions(self):
        prompt = build_feature_prompt(_make_spec())
        assert "ONE AT A TIME" in prompt
        assert "feature-progress" in prompt

    def test_includes_feature_id_in_commit_convention(self):
        prompt = build_feature_prompt(_make_spec(fid="F042"))
        assert "F042" in prompt


class TestCreateBatchDispatchPlan:
    def test_single_feature_plan(self):
        plan = create_batch_dispatch_plan(
            wave_number=1,
            wave_features=["F001"],
            feature_specs={"F001": _make_spec("F001")},
        )
        assert plan["wave_number"] == 1
        assert plan["total_features"] == 1
        assert plan["execution_mode"] == "batch"
        assert len(plan["tasks"]) == 1

    def test_multi_feature_plan(self):
        plan = create_batch_dispatch_plan(
            wave_number=2,
            wave_features=["F001", "F002", "F003"],
            feature_specs={
                "F001": _make_spec("F001"),
                "F002": _make_spec("F002"),
                "F003": _make_spec("F003"),
            },
        )
        assert plan["total_features"] == 3
        assert len(plan["tasks"]) == 3

    def test_worktree_branch_naming(self):
        plan = create_batch_dispatch_plan(
            wave_number=1,
            wave_features=["F001"],
            feature_specs={"F001": _make_spec("F001")},
            project_id="my-project",
        )
        assert plan["tasks"][0]["worktree_branch"] == "rapids/my-project/F001"

    def test_worktree_branch_without_project_id(self):
        plan = create_batch_dispatch_plan(
            wave_number=1,
            wave_features=["F001"],
            feature_specs={"F001": _make_spec("F001")},
        )
        assert plan["tasks"][0]["worktree_branch"] == "rapids/F001"

    def test_context_files_populated(self):
        plan = create_batch_dispatch_plan(
            wave_number=1,
            wave_features=["F001"],
            feature_specs={"F001": _make_spec("F001")},
        )
        context_files = plan["tasks"][0]["context_files"]
        assert ".rapids/context/accumulated.json" in context_files

    def test_execution_mode_always_batch(self):
        plan = create_batch_dispatch_plan(
            wave_number=1,
            wave_features=["F001"],
            feature_specs={"F001": _make_spec("F001")},
        )
        assert plan["execution_mode"] == "batch"

    def test_confirmation_required_true(self):
        plan = create_batch_dispatch_plan(
            wave_number=1,
            wave_features=["F001"],
            feature_specs={"F001": _make_spec("F001")},
        )
        assert plan["confirmation_required"] is True

    def test_empty_wave_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            create_batch_dispatch_plan(
                wave_number=1,
                wave_features=[],
                feature_specs={},
            )

    def test_missing_feature_spec_raises(self):
        with pytest.raises(ValueError, match="Missing feature spec"):
            create_batch_dispatch_plan(
                wave_number=1,
                wave_features=["F001"],
                feature_specs={},
            )

    def test_plugin_mapping_propagated(self):
        plan = create_batch_dispatch_plan(
            wave_number=1,
            wave_features=["F001"],
            feature_specs={"F001": _make_spec("F001", plugin="gcp")},
            feature_plugins={"F001": "rapids-gcp"},
        )
        assert plan["tasks"][0]["plugin"] == "rapids-gcp"

    def test_features_sorted(self):
        plan = create_batch_dispatch_plan(
            wave_number=1,
            wave_features=["F003", "F001", "F002"],
            feature_specs={
                "F001": _make_spec("F001"),
                "F002": _make_spec("F002"),
                "F003": _make_spec("F003"),
            },
        )
        ids = [t["feature_id"] for t in plan["tasks"]]
        assert ids == ["F001", "F002", "F003"]


class TestFormatBatchCommand:
    def test_single_task(self):
        plan = create_batch_dispatch_plan(
            wave_number=1,
            wave_features=["F001"],
            feature_specs={"F001": _make_spec("F001")},
        )
        cmd = format_batch_command(plan)
        assert "F001" in cmd
        assert "---" not in cmd  # Single task, no separator

    def test_multi_task_separator(self):
        plan = create_batch_dispatch_plan(
            wave_number=1,
            wave_features=["F001", "F002"],
            feature_specs={
                "F001": _make_spec("F001"),
                "F002": _make_spec("F002"),
            },
        )
        cmd = format_batch_command(plan)
        assert "---" in cmd
        assert "F001" in cmd
        assert "F002" in cmd

    def test_empty_plan_returns_empty(self):
        cmd = format_batch_command({"tasks": []})
        assert cmd == ""
