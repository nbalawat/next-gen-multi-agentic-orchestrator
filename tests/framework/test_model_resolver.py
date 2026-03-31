"""F1 tests for model resolver. Zero LLM calls."""

import pytest

from rapids_core.model_resolver import resolve_model


class TestModelResolver:
    def test_tier_1_uses_haiku(self):
        result = resolve_model(tier=1, phase="implement")
        assert result.model == "haiku"
        assert result.effort == "low"

    def test_tier_3_analysis_uses_opus(self):
        result = resolve_model(tier=3, phase="analysis")
        assert result.model == "opus"
        assert result.effort == "high"

    def test_tier_3_implement_uses_sonnet(self):
        result = resolve_model(tier=3, phase="implement")
        assert result.model == "sonnet"
        assert result.effort == "medium"

    def test_tier_5_plan_uses_opus(self):
        result = resolve_model(tier=5, phase="plan")
        assert result.model == "opus"

    def test_user_override_takes_precedence(self):
        result = resolve_model(
            tier=3,
            phase="implement",
            user_override={"model": "opus", "effort": "high"},
        )
        assert result.model == "opus"
        assert result.effort == "high"

    def test_plugin_minimum_raises_floor(self):
        result = resolve_model(
            tier=2,
            phase="implement",
            plugin_minimum={"model": "sonnet"},
        )
        assert result.model == "sonnet"

    def test_plugin_minimum_does_not_lower_ceiling(self):
        result = resolve_model(
            tier=3,
            phase="analysis",
            plugin_minimum={"model": "sonnet"},
        )
        # Opus is already higher than sonnet, so no change
        assert result.model == "opus"

    def test_user_override_can_lower_model(self):
        result = resolve_model(
            tier=3,
            phase="analysis",
            user_override={"model": "haiku"},
        )
        assert result.model == "haiku"

    def test_capability_param_accepted(self):
        result = resolve_model(
            tier=3, phase="implement", capability="terraform-authoring"
        )
        assert result.model == "sonnet"

    def test_unknown_tier_phase_uses_fallback(self):
        result = resolve_model(tier=99, phase="unknown")
        assert result.model == "sonnet"
        assert result.effort == "medium"

    def test_max_turns_increases_with_tier(self):
        r3 = resolve_model(tier=3, phase="implement")
        r5 = resolve_model(tier=5, phase="implement")
        assert r5.max_turns >= r3.max_turns

    def test_high_effort_has_more_turns(self):
        r_low = resolve_model(tier=1, phase="implement")
        r_high = resolve_model(tier=3, phase="analysis")
        assert r_high.max_turns >= r_low.max_turns

    def test_tier_4_gets_at_least_100_turns(self):
        result = resolve_model(tier=4, phase="implement")
        assert result.max_turns >= 100

    def test_tier_5_gets_at_least_200_turns(self):
        result = resolve_model(tier=5, phase="implement")
        assert result.max_turns >= 200

    def test_plugin_minimum_effort(self):
        result = resolve_model(
            tier=1,
            phase="implement",
            plugin_minimum={"effort": "high"},
        )
        assert result.effort == "high"

    def test_partial_user_override(self):
        result = resolve_model(
            tier=3,
            phase="implement",
            user_override={"model": "opus"},
        )
        assert result.model == "opus"
        assert result.effort == "medium"  # Not overridden
