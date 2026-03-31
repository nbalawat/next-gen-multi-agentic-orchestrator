import json
from pathlib import Path

import pytest


@pytest.fixture
def rapids_dir(tmp_path):
    """Bare .rapids/ directory with minimal structure."""
    rapids = tmp_path / ".rapids"
    rapids.mkdir()
    (rapids / "phases").mkdir()
    (rapids / "context").mkdir()
    (rapids / "audit").mkdir()
    (rapids / "audit" / "cost.jsonl").touch()
    (rapids / "audit" / "timeline.jsonl").touch()
    return rapids


@pytest.fixture
def rapids_json_factory(rapids_dir):
    """Factory fixture to create rapids.json with specific state."""
    phase_defaults = {
        1: ["implement"],
        2: ["plan", "implement"],
        3: ["analysis", "plan", "implement", "deploy"],
        4: ["research", "analysis", "plan", "implement", "deploy"],
        5: ["research", "analysis", "plan", "implement", "deploy", "sustain"],
    }

    def _create(tier=3, phase="analysis", phases=None, plugins=None, project_id="test"):
        if phases is None:
            phases = phase_defaults.get(tier, ["implement"])
        data = {
            "project": {"id": project_id},
            "scope": {"tier": tier, "phases": phases},
            "current": {"phase": phase},
            "plugins": plugins or [],
        }
        (rapids_dir / "rapids.json").write_text(json.dumps(data, indent=2))
        return data

    return _create


@pytest.fixture
def accumulated_context(rapids_dir):
    """Factory to set accumulated context."""

    def _create(context_dict):
        (rapids_dir / "context" / "accumulated.json").write_text(
            json.dumps(context_dict, indent=2)
        )

    return _create


@pytest.fixture
def sample_feature_spec_xml():
    """Valid feature spec XML for testing."""
    return """<feature id="F001" version="1.0" priority="high" depends_on="" plugin="gcp">
    <n>Test Feature</n>
    <description>A test feature for validation</description>
    <acceptance_criteria>
        <criterion>It passes all tests</criterion>
        <criterion>It handles edge cases</criterion>
    </acceptance_criteria>
    <estimated_complexity>M</estimated_complexity>
</feature>"""


@pytest.fixture
def sample_dependency_graph():
    """A dependency graph with known wave structure."""
    return {
        "features": ["F001", "F002", "F003", "F004", "F005"],
        "dependencies": {
            "F002": ["F001"],
            "F004": ["F003"],
            "F005": ["F002", "F003"],
        },
    }


@pytest.fixture
def sample_signals_factory():
    """Factory for scope classifier input signals."""
    defaults = {
        1: {
            "description": "Fix typo in login error message",
            "files_impacted": 1,
            "new_infrastructure": False,
            "integrations": [],
            "domain_complexity": "low",
        },
        2: {
            "description": "Add due_date field to Todo API",
            "files_impacted": 5,
            "new_infrastructure": False,
            "integrations": [],
            "domain_complexity": "low",
        },
        3: {
            "description": "Build payment dashboard with Bigtable",
            "files_impacted": 15,
            "new_infrastructure": False,
            "integrations": ["bigtable", "react-dashboard"],
            "domain_complexity": "moderate",
        },
        4: {
            "description": "Build multi-service event pipeline with monitoring",
            "files_impacted": 40,
            "new_infrastructure": True,
            "integrations": ["pubsub", "bigtable", "cloud-run"],
            "domain_complexity": "high",
        },
        5: {
            "description": "Build new event-driven payments platform",
            "files_impacted": 100,
            "new_infrastructure": True,
            "integrations": ["pubsub", "bigtable", "dataflow", "cloud-run"],
            "domain_complexity": "high",
        },
    }

    def _create(tier_hint=3, **overrides):
        signals = dict(defaults.get(tier_hint, defaults[3]))
        signals.update(overrides)
        return signals

    return _create


@pytest.fixture
def plugin_dir(tmp_path):
    """Factory to create a plugin directory for governance tests."""

    def _create(name="rapids-test", capabilities=None, overlay_content=None):
        plugin_path = tmp_path / name
        plugin_path.mkdir()
        (plugin_path / ".claude-plugin").mkdir()
        (plugin_path / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": name})
        )
        if capabilities:
            rapids_meta = {"capabilities": capabilities}
            (plugin_path / "rapids.plugin.json").write_text(json.dumps(rapids_meta))
        if overlay_content:
            skill_dir = plugin_path / "skills" / "default"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(overlay_content)
        return plugin_path

    return _create
