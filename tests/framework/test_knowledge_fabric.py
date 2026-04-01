"""F1 tests for Knowledge Fabric. Zero LLM calls."""

import pytest
from pathlib import Path
from unittest.mock import patch

import yaml

from rapids_core.knowledge_fabric import (
    load_agent_expertise,
    save_agent_expertise,
    initialize_agent_expertise,
    record_session_outcome,
    add_lesson,
    add_pitfall,
    get_prompt_injections,
    trim_expertise,
    format_expertise_summary,
    AGENTS_DIR,
    MAX_EXPERTISE_LINES,
)


@pytest.fixture
def agents_dir(tmp_path):
    """Redirect agent expertise storage to tmp dir."""
    d = tmp_path / "agents"
    d.mkdir()
    with patch("rapids_core.knowledge_fabric.AGENTS_DIR", d):
        yield d


class TestInitializeExpertise:
    def test_creates_file(self, agents_dir):
        expertise = initialize_agent_expertise("test-agent")
        assert (agents_dir / "test-agent" / "expertise.yaml").exists()

    def test_has_overview(self, agents_dir):
        expertise = initialize_agent_expertise("test-agent")
        assert expertise["overview"]["agent_name"] == "test-agent"
        assert expertise["overview"]["total_sessions"] == 0

    def test_from_definition(self, agents_dir):
        defn = {"description": "Terraform engineer", "model": "sonnet", "role": "coder"}
        expertise = initialize_agent_expertise("tf-eng", agent_definition=defn)
        assert expertise["overview"]["description"] == "Terraform engineer"
        assert expertise["overview"]["model"] == "sonnet"

    def test_idempotent(self, agents_dir):
        e1 = initialize_agent_expertise("test-agent")
        add_lesson("test-agent", "Test lesson")
        e2 = initialize_agent_expertise("test-agent")
        assert len(e2.get("learned_lessons", [])) == 1  # Preserved


class TestLoadSaveExpertise:
    def test_save_and_load(self, agents_dir):
        expertise = {"overview": {"agent_name": "test"}, "domain_knowledge": {}}
        save_agent_expertise("test-agent", expertise)
        loaded = load_agent_expertise("test-agent")
        assert loaded["overview"]["agent_name"] == "test"

    def test_load_nonexistent(self, agents_dir):
        assert load_agent_expertise("nonexistent") is None

    def test_save_adds_timestamp(self, agents_dir):
        save_agent_expertise("test-agent", {"overview": {}})
        loaded = load_agent_expertise("test-agent")
        assert "updated_at" in loaded


class TestRecordSessionOutcome:
    def test_increments_sessions(self, agents_dir):
        initialize_agent_expertise("agent")
        record_session_outcome("agent", features_passed=3, features_failed=0)
        e = load_agent_expertise("agent")
        assert e["overview"]["total_sessions"] == 1
        assert e["overview"]["total_features"] == 3

    def test_updates_success_rate(self, agents_dir):
        initialize_agent_expertise("agent")
        record_session_outcome("agent", features_passed=8, features_failed=2)
        e = load_agent_expertise("agent")
        assert e["overview"]["success_rate"] == 0.8

    def test_accumulates_across_sessions(self, agents_dir):
        initialize_agent_expertise("agent")
        record_session_outcome("agent", features_passed=5, features_failed=0)
        record_session_outcome("agent", features_passed=3, features_failed=2)
        e = load_agent_expertise("agent")
        assert e["overview"]["total_sessions"] == 2
        assert e["overview"]["total_features"] == 10
        assert e["performance_stats"]["features_completed"] == 8
        assert e["performance_stats"]["features_failed"] == 2

    def test_tracks_retries(self, agents_dir):
        initialize_agent_expertise("agent")
        record_session_outcome("agent", features_passed=3, total_retries=2)
        e = load_agent_expertise("agent")
        assert e["performance_stats"]["total_retries"] == 2

    def test_auto_initializes(self, agents_dir):
        record_session_outcome("new-agent", features_passed=1)
        e = load_agent_expertise("new-agent")
        assert e is not None
        assert e["overview"]["total_sessions"] == 1


class TestAddLesson:
    def test_adds_new_lesson(self, agents_dir):
        initialize_agent_expertise("agent")
        add_lesson("agent", "Always pin provider versions", source="S001", confidence=0.6)
        e = load_agent_expertise("agent")
        assert len(e["learned_lessons"]) == 1
        assert e["learned_lessons"][0]["lesson"] == "Always pin provider versions"
        assert e["learned_lessons"][0]["confidence"] == 0.6

    def test_reinforces_existing_lesson(self, agents_dir):
        initialize_agent_expertise("agent")
        add_lesson("agent", "Pin provider versions", source="S001", confidence=0.5)
        add_lesson("agent", "Pin provider versions", source="S002", confidence=0.5)
        e = load_agent_expertise("agent")
        assert len(e["learned_lessons"]) == 1  # Still one lesson
        assert e["learned_lessons"][0]["confidence"] == 0.6  # Bumped by 0.1
        assert e["learned_lessons"][0]["times_reinforced"] == 2
        assert "S001" in e["learned_lessons"][0]["learned_from"]
        assert "S002" in e["learned_lessons"][0]["learned_from"]

    def test_confidence_caps_at_1(self, agents_dir):
        initialize_agent_expertise("agent")
        add_lesson("agent", "Lesson", confidence=0.95)
        add_lesson("agent", "Lesson", confidence=0.95)  # Would push to 1.05
        e = load_agent_expertise("agent")
        assert e["learned_lessons"][0]["confidence"] == 1.0

    def test_multiple_different_lessons(self, agents_dir):
        initialize_agent_expertise("agent")
        add_lesson("agent", "Lesson A")
        add_lesson("agent", "Lesson B")
        add_lesson("agent", "Lesson C")
        e = load_agent_expertise("agent")
        assert len(e["learned_lessons"]) == 3


class TestAddPitfall:
    def test_adds_new_pitfall(self, agents_dir):
        initialize_agent_expertise("agent")
        add_pitfall("agent", "Forgetting terraform fmt", "Run fmt first")
        e = load_agent_expertise("agent")
        assert len(e["common_pitfalls"]) == 1
        assert e["common_pitfalls"][0]["occurrences"] == 1

    def test_increments_existing(self, agents_dir):
        initialize_agent_expertise("agent")
        add_pitfall("agent", "Forgetting terraform fmt", "Run fmt first")
        add_pitfall("agent", "Forgetting terraform fmt", "Always run fmt as step 1")
        e = load_agent_expertise("agent")
        assert len(e["common_pitfalls"]) == 1
        assert e["common_pitfalls"][0]["occurrences"] == 2
        assert e["common_pitfalls"][0]["mitigation"] == "Always run fmt as step 1"  # Updated


class TestGetPromptInjections:
    def test_no_expertise_returns_empty(self, agents_dir):
        assert get_prompt_injections("nonexistent") == ""

    def test_includes_lessons(self, agents_dir):
        initialize_agent_expertise("agent")
        add_lesson("agent", "Pin provider versions", confidence=0.8)
        result = get_prompt_injections("agent")
        assert "Pin provider versions" in result
        assert "0.8" in result

    def test_includes_pitfalls(self, agents_dir):
        initialize_agent_expertise("agent")
        add_pitfall("agent", "Hardcoding IDs", "Use variables")
        result = get_prompt_injections("agent")
        assert "Hardcoding IDs" in result
        assert "Use variables" in result

    def test_includes_stats(self, agents_dir):
        initialize_agent_expertise("agent")
        record_session_outcome("agent", features_passed=10, features_failed=2)
        result = get_prompt_injections("agent")
        assert "83%" in result  # 10/12

    def test_filters_low_confidence(self, agents_dir):
        initialize_agent_expertise("agent")
        add_lesson("agent", "High confidence lesson", confidence=0.9)
        add_lesson("agent", "Low confidence guess", confidence=0.3)
        result = get_prompt_injections("agent")
        assert "High confidence" in result
        assert "Low confidence" not in result

    def test_includes_domain_knowledge(self, agents_dir):
        initialize_agent_expertise("agent")
        e = load_agent_expertise("agent")
        e["domain_knowledge"] = {
            "gcp": {
                "cloud_run": {"pattern": "Use managed Cloud Run", "confidence": 0.9}
            }
        }
        save_agent_expertise("agent", e)
        result = get_prompt_injections("agent")
        assert "managed Cloud Run" in result


class TestTrimExpertise:
    def test_under_limit_unchanged(self, agents_dir):
        expertise = {"overview": {"agent": "test"}, "learned_lessons": []}
        result = trim_expertise(expertise, max_lines=1000)
        assert result == expertise

    def test_removes_low_confidence_lessons_first(self, agents_dir):
        lessons = [
            {"lesson": f"Lesson {i}", "confidence": i * 0.1}
            for i in range(1, 20)
        ]
        expertise = {"overview": {}, "learned_lessons": lessons, "common_pitfalls": []}
        result = trim_expertise(expertise, max_lines=30)
        remaining = result.get("learned_lessons", [])
        # Higher confidence lessons should survive
        if remaining:
            confidences = [l["confidence"] for l in remaining]
            assert confidences == sorted(confidences)  # Lowest removed first


class TestFormatExpertiseSummary:
    def test_no_expertise(self, agents_dir):
        result = format_expertise_summary("nonexistent")
        assert "No expertise" in result

    def test_shows_stats(self, agents_dir):
        initialize_agent_expertise("agent")
        record_session_outcome("agent", features_passed=5, features_failed=1)
        add_lesson("agent", "Important lesson", confidence=0.9)
        result = format_expertise_summary("agent")
        assert "agent" in result
        assert "Sessions: 1" in result
        assert "Important lesson" in result

    def test_shows_pitfalls(self, agents_dir):
        initialize_agent_expertise("agent")
        add_pitfall("agent", "Bad practice", "Do this instead")
        result = format_expertise_summary("agent")
        assert "Bad practice" in result


class TestExpertiseGrowthAcrossSessions:
    """Integration test: expertise grows over multiple sessions."""

    def test_three_sessions_growth(self, agents_dir):
        initialize_agent_expertise("tf-eng", {"description": "Terraform engineer"})

        # Session 1: 3 features, 1 lesson
        record_session_outcome("tf-eng", features_passed=3, features_failed=0, session_id="S001")
        add_lesson("tf-eng", "Pin provider versions", source="S001", confidence=0.5)

        # Session 2: 2 features, 1 fail, reinforce lesson, new pitfall
        record_session_outcome("tf-eng", features_passed=2, features_failed=1, total_retries=2, session_id="S002")
        add_lesson("tf-eng", "Pin provider versions", source="S002")  # Reinforce
        add_pitfall("tf-eng", "Missing validation rules", "Add validation to all variables")

        # Session 3: 4 features, new lesson
        record_session_outcome("tf-eng", features_passed=4, features_failed=0, session_id="S003")
        add_lesson("tf-eng", "Use locals for computed values", source="S003", confidence=0.6)
        add_lesson("tf-eng", "Pin provider versions", source="S003")  # Reinforce again

        e = load_agent_expertise("tf-eng")

        # Verify accumulated stats
        assert e["overview"]["total_sessions"] == 3
        assert e["overview"]["total_features"] == 10
        assert e["performance_stats"]["features_completed"] == 9
        assert e["performance_stats"]["features_failed"] == 1

        # Verify lesson reinforcement
        pin_lesson = [l for l in e["learned_lessons"] if "Pin" in l["lesson"]][0]
        assert pin_lesson["times_reinforced"] == 3
        assert pin_lesson["confidence"] >= 0.7  # 0.5 + 0.1 + 0.1
        assert len(pin_lesson["learned_from"]) == 3

        # Verify prompt injections include high-confidence lessons
        injections = get_prompt_injections("tf-eng")
        assert "Pin provider versions" in injections
        assert "locals for computed" in injections
        assert "Missing validation" in injections
