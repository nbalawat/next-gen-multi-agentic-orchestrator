"""F1 tests for phase router. Zero LLM calls."""

import pytest

from rapids_core.phase_router import route_phases, ALL_PHASES


class TestPhaseRouter:
    def test_tier_1_implement_only(self):
        assert route_phases(1) == ["implement"]

    def test_tier_2_plan_implement(self):
        assert route_phases(2) == ["plan", "implement"]

    def test_tier_3_includes_analysis_and_deploy(self):
        phases = route_phases(3)
        assert phases == ["analysis", "plan", "implement", "deploy"]

    def test_tier_4_includes_research(self):
        phases = route_phases(4)
        assert "research" in phases
        assert phases[0] == "research"

    def test_tier_5_all_phases(self):
        phases = route_phases(5)
        assert phases == ALL_PHASES

    def test_invalid_tier_zero_raises(self):
        with pytest.raises(ValueError, match="Invalid tier 0"):
            route_phases(0)

    def test_invalid_tier_six_raises(self):
        with pytest.raises(ValueError, match="Invalid tier 6"):
            route_phases(6)

    def test_invalid_tier_negative_raises(self):
        with pytest.raises(ValueError):
            route_phases(-1)

    def test_returns_new_list_each_call(self):
        a = route_phases(3)
        b = route_phases(3)
        assert a == b
        assert a is not b  # Should be independent copies

    def test_all_tiers_end_with_implement(self):
        for tier in range(1, 6):
            phases = route_phases(tier)
            assert "implement" in phases
