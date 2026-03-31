"""F1 tests for dependency graph generator. Zero LLM calls."""

import pytest
from pathlib import Path

from rapids_core.dependency_graph_generator import (
    parse_feature_spec,
    generate_dependency_graph,
    generate_dependency_graph_from_directory,
    FeatureMetadata,
)


def _make_spec(
    fid: str = "F001",
    depends_on: str = "",
    plugin: str = "gcp",
    name: str = "Test Feature",
    priority: str = "high",
    complexity: str = "M",
) -> str:
    return f"""<feature id="{fid}" version="1.0" priority="{priority}" depends_on="{depends_on}" plugin="{plugin}">
    <n>{name}</n>
    <description>Description of {fid}</description>
    <acceptance_criteria>
        <criterion>Criterion 1</criterion>
    </acceptance_criteria>
    <estimated_complexity>{complexity}</estimated_complexity>
</feature>"""


class TestParseFeatureSpec:
    def test_extracts_id_and_name(self):
        meta = parse_feature_spec(_make_spec(fid="F007", name="My Feature"))
        assert meta.feature_id == "F007"
        assert meta.name == "My Feature"

    def test_extracts_depends_on_single(self):
        meta = parse_feature_spec(_make_spec(depends_on="F001"))
        assert meta.depends_on == ["F001"]

    def test_extracts_depends_on_multiple_comma(self):
        meta = parse_feature_spec(_make_spec(depends_on="F001,F002"))
        assert meta.depends_on == ["F001", "F002"]

    def test_extracts_depends_on_multiple_comma_space(self):
        meta = parse_feature_spec(_make_spec(depends_on="F001, F002, F003"))
        assert meta.depends_on == ["F001", "F002", "F003"]

    def test_extracts_depends_on_space_separated(self):
        meta = parse_feature_spec(_make_spec(depends_on="F001 F002"))
        assert meta.depends_on == ["F001", "F002"]

    def test_empty_depends_on_returns_empty_list(self):
        meta = parse_feature_spec(_make_spec(depends_on=""))
        assert meta.depends_on == []

    def test_extracts_plugin_attribute(self):
        meta = parse_feature_spec(_make_spec(plugin="rapids-gcp"))
        assert meta.plugin == "rapids-gcp"

    def test_missing_plugin_defaults_to_empty(self):
        xml = """<feature id="F001" version="1.0" priority="high">
            <n>Test</n><description>Desc</description>
            <acceptance_criteria><criterion>C1</criterion></acceptance_criteria>
        </feature>"""
        meta = parse_feature_spec(xml)
        assert meta.plugin == ""

    def test_extracts_priority_and_complexity(self):
        meta = parse_feature_spec(_make_spec(priority="critical", complexity="XL"))
        assert meta.priority == "critical"
        assert meta.complexity == "XL"

    def test_malformed_xml_raises_value_error(self):
        with pytest.raises(ValueError, match="XML parse error"):
            parse_feature_spec("<not valid xml")

    def test_missing_id_raises_value_error(self):
        xml = """<feature version="1.0" priority="high">
            <n>Test</n><description>Desc</description>
            <acceptance_criteria><criterion>C1</criterion></acceptance_criteria>
        </feature>"""
        with pytest.raises(ValueError, match="missing required 'id'"):
            parse_feature_spec(xml)

    def test_wrong_root_element_raises(self):
        with pytest.raises(ValueError, match="Root element must be 'feature'"):
            parse_feature_spec('<notfeature id="F001"/>')


class TestGenerateDependencyGraph:
    def test_single_feature_no_deps(self):
        graph = generate_dependency_graph([_make_spec("F001")])
        assert graph["features"] == ["F001"]
        assert graph["dependencies"] == {}

    def test_multiple_features_with_deps(self):
        specs = [
            _make_spec("F001"),
            _make_spec("F002", depends_on="F001"),
            _make_spec("F003", depends_on="F001,F002"),
        ]
        graph = generate_dependency_graph(specs)
        assert graph["features"] == ["F001", "F002", "F003"]
        assert graph["dependencies"]["F002"] == ["F001"]
        assert graph["dependencies"]["F003"] == ["F001", "F002"]

    def test_features_sorted_alphabetically(self):
        specs = [_make_spec("F003"), _make_spec("F001"), _make_spec("F002")]
        graph = generate_dependency_graph(specs)
        assert graph["features"] == ["F001", "F002", "F003"]

    def test_duplicate_feature_id_raises(self):
        specs = [_make_spec("F001"), _make_spec("F001", name="Duplicate")]
        with pytest.raises(ValueError, match="Duplicate feature IDs"):
            generate_dependency_graph(specs)

    def test_dependency_on_unknown_feature_raises(self):
        specs = [_make_spec("F001", depends_on="F999")]
        with pytest.raises(ValueError, match="not in the feature set"):
            generate_dependency_graph(specs)

    def test_metadata_includes_plugin_mapping(self):
        specs = [
            _make_spec("F001", plugin="rapids-gcp"),
            _make_spec("F002", plugin="rapids-react"),
        ]
        graph = generate_dependency_graph(specs)
        assert graph["metadata"]["F001"]["plugin"] == "rapids-gcp"
        assert graph["metadata"]["F002"]["plugin"] == "rapids-react"

    def test_empty_input_raises(self):
        with pytest.raises(ValueError, match="No feature specs"):
            generate_dependency_graph([])

    def test_output_validates_with_artifact_validator(self):
        specs = [
            _make_spec("F001"),
            _make_spec("F002", depends_on="F001"),
        ]
        graph = generate_dependency_graph(specs)
        # If we got here without ValueError, validation passed
        assert "features" in graph
        assert "dependencies" in graph

    def test_dependencies_only_for_features_with_deps(self):
        specs = [_make_spec("F001"), _make_spec("F002"), _make_spec("F003", depends_on="F001")]
        graph = generate_dependency_graph(specs)
        assert "F001" not in graph["dependencies"]
        assert "F002" not in graph["dependencies"]
        assert "F003" in graph["dependencies"]


class TestGenerateFromDirectory:
    def test_reads_all_xml_files(self, tmp_path):
        (tmp_path / "F001.xml").write_text(_make_spec("F001"))
        (tmp_path / "F002.xml").write_text(_make_spec("F002", depends_on="F001"))
        graph = generate_dependency_graph_from_directory(str(tmp_path))
        assert graph["features"] == ["F001", "F002"]

    def test_ignores_non_xml_files(self, tmp_path):
        (tmp_path / "F001.xml").write_text(_make_spec("F001"))
        (tmp_path / "README.md").write_text("# Not a feature spec")
        (tmp_path / "notes.txt").write_text("Some notes")
        graph = generate_dependency_graph_from_directory(str(tmp_path))
        assert graph["features"] == ["F001"]

    def test_missing_directory_raises(self):
        with pytest.raises(FileNotFoundError):
            generate_dependency_graph_from_directory("/tmp/nonexistent-dir-12345")

    def test_empty_directory_raises(self, tmp_path):
        with pytest.raises(ValueError, match="No XML files"):
            generate_dependency_graph_from_directory(str(tmp_path))
