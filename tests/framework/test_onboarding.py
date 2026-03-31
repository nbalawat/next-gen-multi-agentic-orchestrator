"""F1 tests for onboarding question builders. Zero LLM calls.

Validates that all question payloads conform to the AskUserQuestion tool schema:
- questions: array of 1-4 items
- Each question has: question (str), header (str, ≤12 chars), options (2-4 items), multiSelect (bool)
- Each option has: label (str), description (str), optional preview (str)
"""

import pytest

from rapids_core.onboarding import (
    workspace_question,
    project_selection_question,
    new_project_directory_question,
    working_directory_question,
    scope_confirmation_question,
    execution_mode_question,
    project_description_question,
    TIER_LABELS,
)


# ─── Schema Validation Helper ────────────────────────────────────────────────

def _validate_ask_user_question_payload(payload: dict) -> None:
    """Assert a payload matches the AskUserQuestion tool schema."""
    assert "questions" in payload, "Payload must have 'questions' key"
    questions = payload["questions"]
    assert isinstance(questions, list), "questions must be a list"
    assert 1 <= len(questions) <= 4, f"Must have 1-4 questions, got {len(questions)}"

    for q in questions:
        # Required fields
        assert "question" in q, "Question must have 'question' field"
        assert isinstance(q["question"], str), "question must be a string"
        assert q["question"].endswith("?") or q["question"].endswith("."), \
            f"question should end with ? or .: {q['question']}"

        assert "header" in q, "Question must have 'header' field"
        assert isinstance(q["header"], str), "header must be a string"
        assert len(q["header"]) <= 12, f"header must be ≤12 chars, got '{q['header']}' ({len(q['header'])})"

        assert "multiSelect" in q, "Question must have 'multiSelect' field"
        assert isinstance(q["multiSelect"], bool), "multiSelect must be a bool"

        assert "options" in q, "Question must have 'options' field"
        options = q["options"]
        assert isinstance(options, list), "options must be a list"
        assert 2 <= len(options) <= 4, f"Must have 2-4 options, got {len(options)}"

        for opt in options:
            assert "label" in opt, "Option must have 'label' field"
            assert isinstance(opt["label"], str), "label must be a string"
            assert "description" in opt, "Option must have 'description' field"
            assert isinstance(opt["description"], str), "description must be a string"

            # preview is optional but must be str if present
            if "preview" in opt:
                assert isinstance(opt["preview"], str), "preview must be a string"


# ─── Workspace Question ──────────────────────────────────────────────────────

class TestWorkspaceQuestion:
    def test_schema_valid_no_workspaces(self):
        payload = workspace_question()
        _validate_ask_user_question_payload(payload)

    def test_schema_valid_with_workspaces(self):
        workspaces = [
            {"name": "ws-1", "path": "/tmp/ws1", "projects": ["p1", "p2"]},
            {"name": "ws-2", "path": "/tmp/ws2", "projects": []},
        ]
        payload = workspace_question(workspaces)
        _validate_ask_user_question_payload(payload)

    def test_no_workspaces_has_create_recommended(self):
        payload = workspace_question()
        first = payload["questions"][0]["options"][0]
        assert "Create" in first["label"]
        assert "Recommended" in first["label"]

    def test_existing_workspace_is_first(self):
        workspaces = [{"name": "my-ws", "path": "/tmp/ws", "projects": ["p1"]}]
        payload = workspace_question(workspaces)
        first = payload["questions"][0]["options"][0]
        assert "my-ws" in first["label"]
        assert "Recommended" in first["label"]

    def test_existing_workspace_has_preview_with_projects(self):
        workspaces = [{"name": "my-ws", "path": "/tmp/ws", "projects": ["proj-a", "proj-b"]}]
        payload = workspace_question(workspaces)
        first = payload["questions"][0]["options"][0]
        assert "preview" in first
        assert "proj-a" in first["preview"]
        assert "proj-b" in first["preview"]

    def test_empty_workspace_preview_shows_no_projects(self):
        workspaces = [{"name": "empty-ws", "path": "/tmp/ws", "projects": []}]
        payload = workspace_question(workspaces)
        first = payload["questions"][0]["options"][0]
        assert "preview" in first
        assert "no projects yet" in first["preview"]

    def test_max_four_options(self):
        workspaces = [
            {"name": f"ws-{i}", "path": f"/tmp/ws{i}", "projects": []}
            for i in range(5)
        ]
        payload = workspace_question(workspaces)
        assert len(payload["questions"][0]["options"]) <= 4

    def test_always_has_no_workspace_option(self):
        payload = workspace_question()
        labels = [opt["label"] for opt in payload["questions"][0]["options"]]
        assert any("No workspace" in l for l in labels)


# ─── Project Selection Question ───────────────────────────────────────────────

class TestProjectSelectionQuestion:
    def test_schema_valid_no_projects(self):
        payload = project_selection_question([], "/tmp/ws")
        _validate_ask_user_question_payload(payload)

    def test_schema_valid_with_projects(self):
        projects = [
            {"name": "proj-a", "path": "/tmp/ws/a", "tier": 3, "phase": "implement", "status": "active"},
        ]
        payload = project_selection_question(projects, "/tmp/ws")
        _validate_ask_user_question_payload(payload)

    def test_existing_projects_listed_as_options(self):
        projects = [
            {"name": "proj-a", "path": "/tmp/ws/a", "tier": 3, "phase": "implement", "status": "active"},
            {"name": "proj-b", "path": "/tmp/ws/b", "tier": 1, "phase": "plan", "status": "active"},
        ]
        payload = project_selection_question(projects, "/tmp/ws")
        labels = [opt["label"] for opt in payload["questions"][0]["options"]]
        assert "proj-a" in labels
        assert "proj-b" in labels

    def test_create_new_always_present(self):
        projects = [
            {"name": "proj-a", "path": "/tmp/ws/a", "tier": 2, "phase": "plan", "status": "active"},
        ]
        payload = project_selection_question(projects, "/tmp/ws")
        labels = [opt["label"] for opt in payload["questions"][0]["options"]]
        assert any("Create new" in l for l in labels)

    def test_create_new_recommended_when_no_projects(self):
        payload = project_selection_question([], "/tmp/ws")
        first = payload["questions"][0]["options"][0]
        assert "Create new" in first["label"]
        assert "Recommended" in first["label"]

    def test_existing_projects_have_previews(self):
        projects = [
            {"name": "proj-a", "path": "/tmp/ws/a", "tier": 3, "phase": "implement", "status": "active"},
        ]
        payload = project_selection_question(projects, "/tmp/ws")
        first = payload["questions"][0]["options"][0]
        assert "preview" in first
        assert "proj-a" in first["preview"]

    def test_max_four_options(self):
        projects = [
            {"name": f"p{i}", "path": f"/tmp/ws/p{i}", "tier": 1, "phase": "implement", "status": "active"}
            for i in range(5)
        ]
        payload = project_selection_question(projects, "/tmp/ws")
        assert len(payload["questions"][0]["options"]) <= 4


class TestNewProjectDirectoryQuestion:
    def test_schema_valid(self):
        payload = new_project_directory_question("/tmp/ws")
        _validate_ask_user_question_payload(payload)

    def test_includes_workspace_path(self):
        payload = new_project_directory_question("/tmp/my-workspace")
        q = payload["questions"][0]["question"]
        assert "/tmp/my-workspace" in q

    def test_has_two_options(self):
        payload = new_project_directory_question("/tmp/ws")
        assert len(payload["questions"][0]["options"]) == 2


# ─── Working Directory Question (standalone) ─────────────────────────────────

class TestWorkingDirectoryQuestion:
    def test_schema_valid(self):
        payload = working_directory_question("/home/user/projects")
        _validate_ask_user_question_payload(payload)

    def test_default_current_dir(self):
        payload = working_directory_question()
        options = payload["questions"][0]["options"]
        assert any("." in opt["description"] for opt in options)

    def test_includes_current_dir_in_description(self):
        payload = working_directory_question("/my/project/dir")
        options = payload["questions"][0]["options"]
        assert any("/my/project/dir" in opt["description"] for opt in options)

    def test_has_three_options(self):
        payload = working_directory_question()
        assert len(payload["questions"][0]["options"]) == 3

    def test_first_option_is_recommended(self):
        payload = working_directory_question()
        first = payload["questions"][0]["options"][0]
        assert "Recommended" in first["label"]

    def test_header_is_short(self):
        payload = working_directory_question()
        assert payload["questions"][0]["header"] == "Directory"

    def test_not_multiselect(self):
        payload = working_directory_question()
        assert payload["questions"][0]["multiSelect"] is False

    def test_standalone_label_in_question(self):
        payload = working_directory_question("/tmp")
        q = payload["questions"][0]["question"]
        assert "standalone" in q


# ─── Scope Confirmation Question ──────────────────────────────────────────────

class TestScopeConfirmationQuestion:
    def test_schema_valid(self):
        payload = scope_confirmation_question(
            tier=3, tier_label="Feature",
            phases=["analysis", "plan", "implement", "deploy"],
            files_impacted=15, integrations=["postgres", "redis"],
        )
        _validate_ask_user_question_payload(payload)

    def test_includes_tier_in_question(self):
        payload = scope_confirmation_question(
            tier=4, tier_label="System",
            phases=["research", "analysis", "plan", "implement", "deploy"],
            files_impacted=40, integrations=["gcp"],
        )
        assert "Tier 4" in payload["questions"][0]["question"]
        assert "System" in payload["questions"][0]["question"]

    def test_includes_phases_in_question(self):
        payload = scope_confirmation_question(
            tier=2, tier_label="Enhancement",
            phases=["plan", "implement"],
            files_impacted=5, integrations=[],
        )
        assert "Plan" in payload["questions"][0]["question"]
        assert "Implement" in payload["questions"][0]["question"]

    def test_first_option_is_recommended(self):
        payload = scope_confirmation_question(
            tier=3, tier_label="Feature",
            phases=["analysis", "plan", "implement", "deploy"],
            files_impacted=15, integrations=[],
        )
        first = payload["questions"][0]["options"][0]
        assert "Recommended" in first["label"]

    def test_has_previews(self):
        payload = scope_confirmation_question(
            tier=3, tier_label="Feature",
            phases=["analysis", "plan", "implement", "deploy"],
            files_impacted=15, integrations=["postgres"],
        )
        for opt in payload["questions"][0]["options"]:
            assert "preview" in opt
            assert len(opt["preview"]) > 0

    def test_all_tiers_produce_valid_payloads(self):
        tier_phases = {
            1: (["implement"], "Bug Fix"),
            2: (["plan", "implement"], "Enhancement"),
            3: (["analysis", "plan", "implement", "deploy"], "Feature"),
            4: (["research", "analysis", "plan", "implement", "deploy"], "System"),
            5: (["research", "analysis", "plan", "implement", "deploy", "sustain"], "Platform"),
        }
        for tier, (phases, label) in tier_phases.items():
            payload = scope_confirmation_question(
                tier=tier, tier_label=label,
                phases=phases, files_impacted=10, integrations=[],
            )
            _validate_ask_user_question_payload(payload)


# ─── Execution Mode Question ─────────────────────────────────────────────────

class TestExecutionModeQuestion:
    def test_schema_valid(self):
        payload = execution_mode_question(3)
        _validate_ask_user_question_payload(payload)

    def test_tier_1_recommends_autonomous(self):
        payload = execution_mode_question(1)
        first = payload["questions"][0]["options"][0]
        assert "Autonomous" in first["label"]
        assert "Recommended" in first["label"]

    def test_tier_2_recommends_autonomous(self):
        payload = execution_mode_question(2)
        first = payload["questions"][0]["options"][0]
        assert "Autonomous" in first["label"]
        assert "Recommended" in first["label"]

    def test_tier_3_recommends_hybrid(self):
        payload = execution_mode_question(3)
        first = payload["questions"][0]["options"][0]
        assert "Hybrid" in first["label"]
        assert "Recommended" in first["label"]

    def test_tier_4_recommends_human_in_the_loop(self):
        payload = execution_mode_question(4)
        first = payload["questions"][0]["options"][0]
        assert "Human-in-the-loop" in first["label"]
        assert "Recommended" in first["label"]

    def test_tier_5_recommends_human_in_the_loop(self):
        payload = execution_mode_question(5)
        first = payload["questions"][0]["options"][0]
        assert "Human-in-the-loop" in first["label"]
        assert "Recommended" in first["label"]

    def test_all_three_modes_present(self):
        for tier in range(1, 6):
            payload = execution_mode_question(tier)
            labels = [opt["label"] for opt in payload["questions"][0]["options"]]
            labels_lower = " ".join(labels).lower()
            assert "autonomous" in labels_lower
            assert "hybrid" in labels_lower
            assert "human-in-the-loop" in labels_lower

    def test_not_multiselect(self):
        payload = execution_mode_question(3)
        assert payload["questions"][0]["multiSelect"] is False


# ─── Project Description Question ────────────────────────────────────────────

class TestProjectDescriptionQuestion:
    def test_schema_valid(self):
        payload = project_description_question()
        _validate_ask_user_question_payload(payload)

    def test_has_four_options(self):
        payload = project_description_question()
        assert len(payload["questions"][0]["options"]) == 4

    def test_includes_common_project_types(self):
        payload = project_description_question()
        labels = [opt["label"] for opt in payload["questions"][0]["options"]]
        labels_text = " ".join(labels).lower()
        assert "application" in labels_text
        assert "feature" in labels_text
        assert "bug" in labels_text

    def test_not_multiselect(self):
        payload = project_description_question()
        assert payload["questions"][0]["multiSelect"] is False


# ─── Tier Labels ──────────────────────────────────────────────────────────────

class TestTierLabels:
    def test_all_tiers_have_labels(self):
        for tier in range(1, 6):
            assert tier in TIER_LABELS
            assert isinstance(TIER_LABELS[tier], str)
            assert len(TIER_LABELS[tier]) > 0
