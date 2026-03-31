"""F3 tests: Recorded replay against current framework. Zero LLM calls."""

import pytest
from pathlib import Path

from rapids_core.recording import load_recording, create_synthetic_recording
from rapids_core.scope_classifier import classify_scope
from rapids_core.wave_computer import compute_waves
from rapids_core.claude_md_generator import generate_claude_md


RECORDINGS_DIR = Path(__file__).parent / "recordings"


class TestRecordedReplay:
    @pytest.fixture
    def recording(self):
        return load_recording(RECORDINGS_DIR / "synthetic-tier3")

    def test_recording_loads(self, recording):
        assert len(recording.steps) > 0
        assert recording.metadata.get("synthetic") is True

    def test_scope_classification_matches(self, recording):
        onboard_step = recording.get_step("onboard")
        assert onboard_step is not None
        result = classify_scope(onboard_step.input)
        assert result.tier == onboard_step.output["tier"]

    def test_wave_computation_matches(self, recording):
        wave_step = recording.get_step("wave_computation")
        assert wave_step is not None
        result = compute_waves(wave_step.input)
        expected_waves = wave_step.output["waves"]
        assert result == expected_waves

    def test_claude_md_generation_produces_output(self, recording):
        config = {
            "phase": "analysis",
            "tier": 3,
            "plugins": ["rapids-gcp", "rapids-react"],
        }
        result = generate_claude_md(config)
        assert "ANALYSIS" in result
        assert len(result.split("\n")) < 200

    def test_all_hook_steps_have_events(self, recording):
        hook_steps = recording.get_steps("hook")
        for step in hook_steps:
            assert step.event, f"Hook step {step.step} missing event"

    def test_phase_transitions_are_ordered(self, recording):
        transitions = recording.get_steps("phase_transition")
        phases = [t.phase for t in transitions]
        # Should go from earlier to later phases
        expected_order = ["plan", "implement"]
        assert phases == expected_order

    def test_artifacts_present(self, recording):
        content = recording.get_artifact_content("phases/analysis/solution-design.md")
        assert content is not None
        assert "Payment Dashboard" in content


class TestSyntheticRecording:
    def test_create_synthetic(self):
        recording = create_synthetic_recording(
            steps=[
                {"step": 1, "type": "onboard", "input": {"description": "Test"},
                 "output": {"tier": 1}},
            ]
        )
        assert len(recording.steps) == 1
        assert recording.metadata.get("synthetic") is True

    def test_synthetic_with_artifacts(self):
        recording = create_synthetic_recording(
            steps=[{"step": 1, "type": "test"}],
            artifacts={"test.md": "# Test content"},
        )
        assert recording.get_artifact_content("test.md") == "# Test content"

    def test_get_step_returns_none_for_missing(self):
        recording = create_synthetic_recording(
            steps=[{"step": 1, "type": "onboard"}]
        )
        assert recording.get_step("nonexistent") is None

    def test_get_steps_with_filter(self):
        recording = create_synthetic_recording(
            steps=[
                {"step": 1, "type": "hook", "event": "SessionStart"},
                {"step": 2, "type": "hook", "event": "PostToolUse"},
                {"step": 3, "type": "hook", "event": "SessionStart"},
            ]
        )
        result = recording.get_steps("hook", event="SessionStart")
        assert len(result) == 2
