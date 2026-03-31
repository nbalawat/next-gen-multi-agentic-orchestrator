"""F1 tests for wave executor. Zero LLM calls."""

import pytest

from rapids_core.wave_executor import choose_execution_method


class TestWaveExecutor:
    def test_independent_features_use_batch(self):
        result = choose_execution_method(
            wave_features=["F001", "F003"],
            dependency_graph={"features": ["F001", "F003"], "dependencies": {}},
            tier=3,
        )
        assert result == "batch"

    def test_tier_4_always_agent_teams(self):
        result = choose_execution_method(
            wave_features=["F001", "F002"],
            dependency_graph={"features": ["F001", "F002"], "dependencies": {}},
            tier=4,
        )
        assert result == "agent_teams"

    def test_tier_5_always_agent_teams(self):
        result = choose_execution_method(
            wave_features=["F001"],
            dependency_graph={"features": ["F001"], "dependencies": {}},
            tier=5,
        )
        assert result == "agent_teams"

    def test_single_feature_uses_batch(self):
        result = choose_execution_method(
            wave_features=["F001"],
            dependency_graph={"features": ["F001"], "dependencies": {}},
            tier=3,
        )
        assert result == "batch"

    def test_multi_plugin_uses_agent_teams(self):
        result = choose_execution_method(
            wave_features=["F001", "F002"],
            dependency_graph={"features": ["F001", "F002"], "dependencies": {}},
            tier=3,
            feature_plugins={"F001": "rapids-gcp", "F002": "rapids-react"},
        )
        assert result == "agent_teams"

    def test_same_plugin_uses_batch(self):
        result = choose_execution_method(
            wave_features=["F001", "F002"],
            dependency_graph={"features": ["F001", "F002"], "dependencies": {}},
            tier=2,
            feature_plugins={"F001": "rapids-gcp", "F002": "rapids-gcp"},
        )
        assert result == "batch"

    def test_intra_wave_deps_use_agent_teams(self):
        result = choose_execution_method(
            wave_features=["F001", "F002"],
            dependency_graph={
                "features": ["F001", "F002"],
                "dependencies": {"F002": ["F001"]},
            },
            tier=3,
        )
        assert result == "agent_teams"

    def test_default_tier_3(self):
        result = choose_execution_method(
            wave_features=["F001", "F002"],
            dependency_graph={"features": ["F001", "F002"], "dependencies": {}},
        )
        assert result == "batch"

    def test_no_plugins_defaults_to_batch(self):
        result = choose_execution_method(
            wave_features=["F001", "F002"],
            dependency_graph={"features": ["F001", "F002"], "dependencies": {}},
            tier=2,
        )
        assert result == "batch"
