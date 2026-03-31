"""F1 tests for CLAUDE.md generator. Zero LLM calls."""

import pytest

from rapids_core.claude_md_generator import generate_claude_md


class TestClaudeMdGenerator:
    def test_analysis_phase_includes_instructions(self):
        config = {"phase": "analysis", "tier": 3, "plugins": []}
        result = generate_claude_md(config)
        assert "ANALYSIS PHASE" in result
        assert "Solution design" in result

    def test_implement_phase_includes_instructions(self):
        config = {"phase": "implement", "tier": 3, "plugins": []}
        result = generate_claude_md(config)
        assert "IMPLEMENT PHASE" in result
        assert "acceptance criterion" in result

    def test_includes_project_context(self):
        config = {"phase": "analysis", "tier": 3, "plugins": [], "project_id": "my-project"}
        result = generate_claude_md(config)
        assert "my-project" in result
        assert "Tier:** 3" in result

    def test_includes_plugin_overlays(self):
        config = {
            "phase": "analysis",
            "tier": 3,
            "plugins": ["rapids-gcp", "rapids-react"],
        }
        overlays = {
            "rapids-gcp": "Consider GCP services for infrastructure.",
            "rapids-react": "Design component hierarchy first.",
        }
        result = generate_claude_md(config, plugin_overlays=overlays)
        assert "Consider GCP services" in result
        assert "Design component hierarchy" in result

    def test_includes_accumulated_context(self):
        config = {
            "phase": "plan",
            "tier": 3,
            "plugins": [],
            "accumulated_context": {"key_decisions": ["Use Bigtable", "Prefer Cloud Run"]},
        }
        result = generate_claude_md(config)
        assert "Use Bigtable" in result
        assert "Prefer Cloud Run" in result

    def test_includes_constraints(self):
        config = {
            "phase": "analysis",
            "tier": 3,
            "plugins": [],
            "accumulated_context": {"constraints": ["Budget under $50/month"]},
        }
        result = generate_claude_md(config)
        assert "Budget under $50/month" in result

    def test_tier_1_generates_minimal_output(self):
        config = {"phase": "implement", "tier": 1, "plugins": []}
        result = generate_claude_md(config)
        assert len(result.split("\n")) < 50

    def test_under_200_lines(self):
        # Create a config with lots of overlays to test truncation
        config = {
            "phase": "analysis",
            "tier": 5,
            "plugins": [f"plugin-{i}" for i in range(20)],
            "accumulated_context": {
                "key_decisions": [f"Decision {i}" for i in range(50)],
                "constraints": [f"Constraint {i}" for i in range(50)],
            },
        }
        overlays = {f"plugin-{i}": f"Overlay content for plugin {i}.\n" * 10 for i in range(20)}
        result = generate_claude_md(config, plugin_overlays=overlays)
        assert len(result.split("\n")) <= 202  # 200 + possible trailing lines

    def test_no_overlays_for_unlisted_plugins(self):
        config = {"phase": "analysis", "tier": 3, "plugins": ["rapids-gcp"]}
        overlays = {
            "rapids-gcp": "GCP guidance",
            "rapids-react": "React guidance — should NOT appear",
        }
        result = generate_claude_md(config, plugin_overlays=overlays)
        assert "GCP guidance" in result
        assert "should NOT appear" not in result

    def test_empty_config_defaults(self):
        result = generate_claude_md({})
        assert "IMPLEMENT PHASE" in result  # Default phase

    def test_all_phases_have_instructions(self):
        for phase in ["research", "analysis", "plan", "implement", "deploy", "sustain"]:
            config = {"phase": phase, "tier": 3, "plugins": []}
            result = generate_claude_md(config)
            assert phase.upper() in result

    def test_header_present(self):
        result = generate_claude_md({"phase": "implement", "tier": 1, "plugins": []})
        assert "CLAUDE.md" in result
        assert "RAPIDS" in result
