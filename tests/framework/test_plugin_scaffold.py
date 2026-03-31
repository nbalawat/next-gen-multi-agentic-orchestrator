"""F1 tests for plugin scaffold generator. Zero LLM calls."""

import pytest

from rapids_core.plugin_scaffold import generate_plugin_scaffold
from rapids_core.plugin_governance import validate_plugin


class TestPluginScaffold:
    def test_generates_valid_plugin(self, tmp_path):
        path = generate_plugin_scaffold(tmp_path, name="rapids-python")
        result = validate_plugin(path)
        assert result.valid is True

    def test_creates_correct_structure(self, tmp_path):
        path = generate_plugin_scaffold(tmp_path, name="rapids-go")
        assert (path / ".claude-plugin" / "plugin.json").is_file()
        assert (path / "rapids.plugin.json").is_file()
        assert (path / "skills").is_dir()

    def test_manifest_has_name(self, tmp_path):
        import json
        path = generate_plugin_scaffold(tmp_path, name="rapids-rust")
        manifest = json.loads((path / ".claude-plugin" / "plugin.json").read_text())
        assert manifest["name"] == "rapids-rust"

    def test_custom_description(self, tmp_path):
        import json
        path = generate_plugin_scaffold(
            tmp_path, name="rapids-java", description="Java Spring Boot plugin"
        )
        manifest = json.loads((path / ".claude-plugin" / "plugin.json").read_text())
        assert manifest["description"] == "Java Spring Boot plugin"

    def test_custom_capabilities(self, tmp_path):
        import json
        caps = {
            "analysis": [{"id": "java-arch", "description": "Java architecture"}],
            "implement": [{"id": "java-impl", "description": "Java implementation"}],
        }
        path = generate_plugin_scaffold(
            tmp_path, name="rapids-java", capabilities=caps
        )
        meta = json.loads((path / "rapids.plugin.json").read_text())
        assert "analysis" in meta["capabilities"]
        assert "implement" in meta["capabilities"]

    def test_skill_md_exists(self, tmp_path):
        path = generate_plugin_scaffold(tmp_path, name="rapids-python")
        skill_dirs = list((path / "skills").iterdir())
        assert len(skill_dirs) == 1
        assert (skill_dirs[0] / "SKILL.md").is_file()

    def test_idempotent(self, tmp_path):
        generate_plugin_scaffold(tmp_path, name="rapids-test")
        generate_plugin_scaffold(tmp_path, name="rapids-test")  # Should not error
        result = validate_plugin(tmp_path / "rapids-test")
        assert result.valid is True
