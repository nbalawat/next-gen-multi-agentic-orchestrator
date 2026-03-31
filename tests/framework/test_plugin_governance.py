"""F1 tests for plugin governance. Zero LLM calls."""

import json

import pytest

from rapids_core.plugin_governance import validate_plugin, detect_capability_collisions


class TestValidatePlugin:
    def test_valid_minimal_plugin_passes(self, plugin_dir):
        path = plugin_dir(name="rapids-test")
        result = validate_plugin(path)
        assert result.valid is True

    def test_missing_directory_fails(self, tmp_path):
        result = validate_plugin(tmp_path / "nonexistent")
        assert result.valid is False
        assert "not found" in result.error

    def test_missing_manifest_fails(self, tmp_path):
        plugin_path = tmp_path / "bad-plugin"
        plugin_path.mkdir()
        result = validate_plugin(plugin_path)
        assert result.valid is False
        assert "plugin.json" in result.error

    def test_invalid_json_manifest_fails(self, tmp_path):
        plugin_path = tmp_path / "bad-json"
        plugin_path.mkdir()
        (plugin_path / ".claude-plugin").mkdir()
        (plugin_path / ".claude-plugin" / "plugin.json").write_text("{bad json")
        result = validate_plugin(plugin_path)
        assert result.valid is False
        assert "Invalid" in result.error

    def test_missing_name_in_manifest_fails(self, tmp_path):
        plugin_path = tmp_path / "no-name"
        plugin_path.mkdir()
        (plugin_path / ".claude-plugin").mkdir()
        (plugin_path / ".claude-plugin" / "plugin.json").write_text("{}")
        result = validate_plugin(plugin_path)
        assert result.valid is False
        assert "name" in result.error

    def test_skill_dir_missing_skill_md_warns(self, tmp_path):
        path = tmp_path / "bad-skill"
        path.mkdir()
        (path / ".claude-plugin").mkdir()
        (path / ".claude-plugin" / "plugin.json").write_text('{"name": "bad-skill"}')
        skill_dir = path / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        # No SKILL.md in the skill directory
        result = validate_plugin(path)
        assert result.valid is True
        assert any("SKILL.md" in w for w in result.warnings)

    def test_absolute_directive_warns(self, plugin_dir):
        path = plugin_dir(
            name="abs-plugin",
            overlay_content="---\nname: test\n---\nYou MUST always use Cloud Functions",
        )
        result = validate_plugin(path)
        assert result.valid is True
        assert any("absolute directive" in w for w in result.warnings)

    def test_valid_rapids_plugin_json(self, plugin_dir):
        path = plugin_dir(
            name="rapids-gcp",
            capabilities={
                "analysis": [{"id": "gcp-arch", "description": "GCP architecture"}],
            },
        )
        result = validate_plugin(path)
        assert result.valid is True

    def test_invalid_rapids_plugin_json_fails(self, tmp_path):
        path = tmp_path / "bad-meta"
        path.mkdir()
        (path / ".claude-plugin").mkdir()
        (path / ".claude-plugin" / "plugin.json").write_text('{"name": "bad-meta"}')
        (path / "rapids.plugin.json").write_text("{invalid json")
        result = validate_plugin(path)
        assert result.valid is False

    def test_empty_agent_warns(self, tmp_path):
        path = tmp_path / "empty-agent"
        path.mkdir()
        (path / ".claude-plugin").mkdir()
        (path / ".claude-plugin" / "plugin.json").write_text('{"name": "empty-agent"}')
        (path / "agents").mkdir()
        (path / "agents" / "my-agent.md").write_text("")
        result = validate_plugin(path)
        assert result.valid is True
        assert any("empty" in w for w in result.warnings)


class TestCapabilityCollisions:
    def test_no_collision_when_different_ids(self, plugin_dir):
        new = plugin_dir(
            name="new-plugin",
            capabilities={"analysis": [{"id": "new-cap", "description": "New"}]},
        )
        existing = plugin_dir(
            name="existing-plugin",
            capabilities={"analysis": [{"id": "existing-cap", "description": "Existing"}]},
        )
        collisions = detect_capability_collisions(new, [existing])
        assert collisions == []

    def test_collision_detected(self, plugin_dir):
        new = plugin_dir(
            name="new-plugin",
            capabilities={"analysis": [{"id": "shared-cap", "description": "Same ID"}]},
        )
        existing = plugin_dir(
            name="existing-plugin",
            capabilities={"analysis": [{"id": "shared-cap", "description": "Same ID"}]},
        )
        collisions = detect_capability_collisions(new, [existing])
        assert len(collisions) == 1
        assert collisions[0]["capability_id"] == "shared-cap"

    def test_same_id_different_phase_no_collision(self, plugin_dir):
        new = plugin_dir(
            name="new-plugin",
            capabilities={"analysis": [{"id": "cap-1", "description": "Analysis"}]},
        )
        existing = plugin_dir(
            name="existing-plugin",
            capabilities={"implement": [{"id": "cap-1", "description": "Implement"}]},
        )
        collisions = detect_capability_collisions(new, [existing])
        assert collisions == []

    def test_no_rapids_plugin_json_no_collision(self, plugin_dir):
        new = plugin_dir(name="new-plugin")  # No capabilities
        existing = plugin_dir(
            name="existing-plugin",
            capabilities={"analysis": [{"id": "cap-1", "description": "Analysis"}]},
        )
        collisions = detect_capability_collisions(new, [existing])
        assert collisions == []
