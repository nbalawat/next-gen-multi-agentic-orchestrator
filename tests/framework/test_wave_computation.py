"""F1 tests for wave computation. Zero LLM calls."""

import pytest

from rapids_core.wave_computer import compute_waves, CircularDependencyError


class TestWaveComputation:
    def test_independent_features_same_wave(self):
        graph = {"features": ["F001", "F003"], "dependencies": {}}
        waves = compute_waves(graph)
        assert len(waves) == 1
        assert set(waves[0]) == {"F001", "F003"}

    def test_dependent_features_sequential_waves(self, sample_dependency_graph):
        waves = compute_waves(sample_dependency_graph)
        assert waves[0] == ["F001", "F003"]  # No deps
        assert waves[1] == ["F002", "F004"]  # Deps on wave 0
        assert waves[2] == ["F005"]  # Deps on wave 0 + 1

    def test_linear_chain(self):
        graph = {
            "features": ["A", "B", "C"],
            "dependencies": {"B": ["A"], "C": ["B"]},
        }
        waves = compute_waves(graph)
        assert waves == [["A"], ["B"], ["C"]]

    def test_circular_dependency_detected(self):
        graph = {
            "features": ["F001", "F002"],
            "dependencies": {"F001": ["F002"], "F002": ["F001"]},
        }
        with pytest.raises(CircularDependencyError):
            compute_waves(graph)

    def test_self_dependency_detected(self):
        graph = {
            "features": ["F001", "F002"],
            "dependencies": {"F001": ["F001"]},
        }
        # Self-dep means in-degree never reaches 0
        with pytest.raises(CircularDependencyError):
            compute_waves(graph)

    def test_empty_feature_list(self):
        graph = {"features": [], "dependencies": {}}
        assert compute_waves(graph) == []

    def test_single_feature_no_deps(self):
        graph = {"features": ["F001"], "dependencies": {}}
        waves = compute_waves(graph)
        assert waves == [["F001"]]

    def test_diamond_dependency(self):
        graph = {
            "features": ["A", "B", "C", "D"],
            "dependencies": {"B": ["A"], "C": ["A"], "D": ["B", "C"]},
        }
        waves = compute_waves(graph)
        assert waves[0] == ["A"]
        assert set(waves[1]) == {"B", "C"}
        assert waves[2] == ["D"]

    def test_missing_dependency_target_raises(self):
        graph = {
            "features": ["F001"],
            "dependencies": {"F001": ["MISSING"]},
        }
        with pytest.raises(ValueError, match="MISSING"):
            compute_waves(graph)

    def test_features_sorted_within_wave(self):
        graph = {"features": ["C", "A", "B"], "dependencies": {}}
        waves = compute_waves(graph)
        assert waves[0] == ["A", "B", "C"]

    def test_three_level_chain(self):
        graph = {
            "features": ["F001", "F002", "F003", "F004"],
            "dependencies": {
                "F002": ["F001"],
                "F003": ["F001"],
                "F004": ["F002", "F003"],
            },
        }
        waves = compute_waves(graph)
        assert len(waves) == 3

    def test_no_dependencies_key(self):
        graph = {"features": ["A", "B"]}
        waves = compute_waves(graph)
        assert waves == [["A", "B"]]
