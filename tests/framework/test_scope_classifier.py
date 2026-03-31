"""F1 tests for scope classifier. Zero LLM calls."""

import pytest

from rapids_core.scope_classifier import classify_scope


class TestScopeClassifier:
    def test_bug_fix_classifies_tier_1(self, sample_signals_factory):
        signals = sample_signals_factory(1)
        result = classify_scope(signals)
        assert result.tier == 1
        assert result.phases == ["implement"]

    def test_minimal_signals_tier_1(self):
        signals = {
            "description": "Fix typo",
            "files_impacted": 1,
            "new_infrastructure": False,
            "integrations": [],
            "domain_complexity": "low",
        }
        result = classify_scope(signals)
        assert result.tier == 1

    def test_small_enhancement_tier_2(self):
        signals = {
            "description": "Add due_date field to Todo API",
            "files_impacted": 8,
            "new_infrastructure": False,
            "integrations": ["database"],
            "domain_complexity": "low",
        }
        result = classify_scope(signals)
        assert result.tier == 2
        assert result.phases == ["plan", "implement"]

    def test_medium_project_tier_3(self, sample_signals_factory):
        signals = sample_signals_factory(3)
        result = classify_scope(signals)
        assert result.tier == 3
        assert "analysis" in result.phases
        assert "implement" in result.phases

    def test_large_project_tier_4(self, sample_signals_factory):
        signals = sample_signals_factory(4)
        result = classify_scope(signals)
        assert result.tier >= 4
        assert "research" in result.phases

    def test_greenfield_platform_tier_5(self, sample_signals_factory):
        signals = sample_signals_factory(5)
        result = classify_scope(signals)
        assert result.tier == 5
        assert "research" in result.phases
        assert "sustain" in result.phases

    def test_two_integrations_bumps_tier(self):
        signals = {
            "description": "Dashboard with two integrations",
            "files_impacted": 10,
            "new_infrastructure": False,
            "integrations": ["bigtable", "react"],
            "domain_complexity": "low",
        }
        result = classify_scope(signals)
        assert result.tier >= 2

    def test_new_infrastructure_bumps_tier(self):
        signals = {
            "description": "Set up new service",
            "files_impacted": 5,
            "new_infrastructure": True,
            "integrations": [],
            "domain_complexity": "low",
        }
        result = classify_scope(signals)
        assert result.tier >= 2

    def test_high_complexity_bumps_tier(self):
        signals = {
            "description": "Complex domain logic",
            "files_impacted": 5,
            "new_infrastructure": False,
            "integrations": [],
            "domain_complexity": "high",
        }
        result = classify_scope(signals)
        assert result.tier >= 2

    def test_empty_signals_defaults_tier_1(self):
        result = classify_scope({})
        assert result.tier == 1

    def test_result_has_reasoning(self, sample_signals_factory):
        signals = sample_signals_factory(3)
        result = classify_scope(signals)
        assert result.reasoning  # Non-empty reasoning

    def test_phases_are_ordered(self, sample_signals_factory):
        signals = sample_signals_factory(5)
        result = classify_scope(signals)
        all_phases = ["research", "analysis", "plan", "implement", "deploy", "sustain"]
        indices = [all_phases.index(p) for p in result.phases]
        assert indices == sorted(indices)

    def test_many_files_increases_tier(self):
        base = {
            "description": "Change",
            "new_infrastructure": False,
            "integrations": [],
            "domain_complexity": "low",
        }
        r1 = classify_scope({**base, "files_impacted": 1})
        r2 = classify_scope({**base, "files_impacted": 50})
        assert r2.tier > r1.tier

    def test_many_integrations_increases_tier(self):
        base = {
            "description": "Build system",
            "files_impacted": 10,
            "new_infrastructure": False,
            "domain_complexity": "low",
        }
        r1 = classify_scope({**base, "integrations": []})
        r2 = classify_scope({**base, "integrations": ["a", "b", "c", "d"]})
        assert r2.tier > r1.tier
