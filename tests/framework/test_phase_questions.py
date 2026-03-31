"""F1 tests for phase question builders. Zero LLM calls.

Validates all AskUserQuestion payloads from phase interactions conform
to the tool schema.
"""

import pytest

from rapids_core.phase_questions import (
    phase_transition_question,
    wave_plan_question,
    wave_boundary_question,
    evaluator_failure_question,
    deploy_target_question,
    research_focus_question,
)


def _validate_ask_user_question_payload(payload: dict) -> None:
    """Assert a payload matches the AskUserQuestion tool schema."""
    assert "questions" in payload
    questions = payload["questions"]
    assert isinstance(questions, list)
    assert 1 <= len(questions) <= 4

    for q in questions:
        assert "question" in q and isinstance(q["question"], str)
        assert "header" in q and isinstance(q["header"], str)
        assert len(q["header"]) <= 12, f"header too long: '{q['header']}'"
        assert "multiSelect" in q and isinstance(q["multiSelect"], bool)
        assert "options" in q and isinstance(q["options"], list)
        assert 2 <= len(q["options"]) <= 4

        for opt in q["options"]:
            assert "label" in opt and isinstance(opt["label"], str)
            assert "description" in opt and isinstance(opt["description"], str)


class TestPhaseTransitionQuestion:
    def test_schema_valid(self):
        payload = phase_transition_question("analysis", "plan")
        _validate_ask_user_question_payload(payload)

    def test_includes_phase_names(self):
        payload = phase_transition_question("research", "analysis")
        q = payload["questions"][0]["question"]
        assert "Research" in q
        assert "Analysis" in q

    def test_first_option_recommended(self):
        payload = phase_transition_question("plan", "implement")
        assert "Recommended" in payload["questions"][0]["options"][0]["label"]

    def test_all_phase_pairs(self):
        pairs = [
            ("research", "analysis"),
            ("analysis", "plan"),
            ("plan", "implement"),
            ("implement", "deploy"),
            ("deploy", "sustain"),
        ]
        for from_p, to_p in pairs:
            payload = phase_transition_question(from_p, to_p)
            _validate_ask_user_question_payload(payload)


class TestWavePlanQuestion:
    def test_schema_valid(self):
        payload = wave_plan_question(3, 8)
        _validate_ask_user_question_payload(payload)

    def test_includes_counts(self):
        payload = wave_plan_question(5, 12)
        q = payload["questions"][0]["question"]
        assert "5" in q
        assert "12" in q

    def test_single_wave(self):
        payload = wave_plan_question(1, 2)
        _validate_ask_user_question_payload(payload)


class TestWaveBoundaryQuestion:
    def test_schema_valid(self):
        payload = wave_boundary_question(1, 2, 3, 3)
        _validate_ask_user_question_payload(payload)

    def test_includes_wave_numbers(self):
        payload = wave_boundary_question(2, 3, 4, 5)
        q = payload["questions"][0]["question"]
        assert "Wave 2" in q
        assert "4/5" in q

    def test_partial_pass(self):
        payload = wave_boundary_question(1, 2, 2, 3)
        q = payload["questions"][0]["question"]
        assert "2/3" in q


class TestEvaluatorFailureQuestion:
    def test_schema_valid(self):
        payload = evaluator_failure_question("F003")
        _validate_ask_user_question_payload(payload)

    def test_includes_feature_id(self):
        payload = evaluator_failure_question("F007")
        q = payload["questions"][0]["question"]
        assert "F007" in q

    def test_includes_retry_count(self):
        payload = evaluator_failure_question("F001", max_retries=5)
        q = payload["questions"][0]["question"]
        assert "5" in q

    def test_default_retries(self):
        payload = evaluator_failure_question("F001")
        q = payload["questions"][0]["question"]
        assert "3" in q


class TestDeployTargetQuestion:
    def test_schema_valid(self):
        payload = deploy_target_question()
        _validate_ask_user_question_payload(payload)

    def test_staging_recommended(self):
        payload = deploy_target_question()
        first = payload["questions"][0]["options"][0]
        assert "Staging" in first["label"]
        assert "Recommended" in first["label"]

    def test_has_three_targets(self):
        payload = deploy_target_question()
        assert len(payload["questions"][0]["options"]) == 3


class TestResearchFocusQuestion:
    def test_schema_valid(self):
        payload = research_focus_question()
        _validate_ask_user_question_payload(payload)

    def test_is_multiselect(self):
        payload = research_focus_question()
        assert payload["questions"][0]["multiSelect"] is True

    def test_analysis_phase(self):
        payload = research_focus_question("analysis")
        q = payload["questions"][0]["question"]
        assert "Analysis" in q

    def test_has_four_focus_areas(self):
        payload = research_focus_question()
        assert len(payload["questions"][0]["options"]) == 4
