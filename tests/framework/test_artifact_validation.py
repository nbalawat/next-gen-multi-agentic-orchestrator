"""F1 tests for artifact validation. Zero LLM calls."""

import pytest

from rapids_core.artifact_validator import (
    validate_feature_spec,
    validate_dependency_graph,
    validate_journal_entry,
)


class TestFeatureSpecValidation:
    def test_valid_spec_passes(self, sample_feature_spec_xml):
        result = validate_feature_spec(sample_feature_spec_xml)
        assert result.valid is True

    def test_invalid_xml_fails(self):
        result = validate_feature_spec("<not valid xml>><")
        assert result.valid is False
        assert "parse error" in result.error.lower()

    def test_wrong_root_element_fails(self):
        xml = '<task id="T1"><n>Name</n></task>'
        result = validate_feature_spec(xml)
        assert result.valid is False
        assert "feature" in result.error

    def test_missing_id_attribute_fails(self):
        xml = """<feature version="1.0" priority="high" depends_on="" plugin="gcp">
            <n>Name</n>
            <description>Desc</description>
            <acceptance_criteria><criterion>C1</criterion></acceptance_criteria>
        </feature>"""
        result = validate_feature_spec(xml)
        assert result.valid is False
        assert "id" in result.error

    def test_missing_name_fails(self):
        xml = """<feature id="F001" version="1.0" priority="high">
            <description>Desc</description>
            <acceptance_criteria><criterion>C1</criterion></acceptance_criteria>
        </feature>"""
        result = validate_feature_spec(xml)
        assert result.valid is False
        assert "name" in result.error.lower() or "<n>" in result.error

    def test_missing_description_fails(self):
        xml = """<feature id="F001" version="1.0" priority="high">
            <n>Name</n>
            <acceptance_criteria><criterion>C1</criterion></acceptance_criteria>
        </feature>"""
        result = validate_feature_spec(xml)
        assert result.valid is False
        assert "description" in result.error.lower()

    def test_missing_acceptance_criteria_fails(self):
        xml = """<feature id="F001" version="1.0" priority="high">
            <n>Name</n>
            <description>Desc</description>
            <estimated_complexity>M</estimated_complexity>
        </feature>"""
        result = validate_feature_spec(xml)
        assert result.valid is False
        assert "acceptance_criteria" in result.error

    def test_empty_acceptance_criteria_fails(self):
        xml = """<feature id="F001" version="1.0" priority="high">
            <n>Name</n>
            <description>Desc</description>
            <acceptance_criteria></acceptance_criteria>
        </feature>"""
        result = validate_feature_spec(xml)
        assert result.valid is False
        assert "criterion" in result.error.lower()

    def test_invalid_complexity_warns(self):
        xml = """<feature id="F001" version="1.0" priority="high">
            <n>Name</n>
            <description>Desc</description>
            <acceptance_criteria><criterion>C1</criterion></acceptance_criteria>
            <estimated_complexity>HUGE</estimated_complexity>
        </feature>"""
        result = validate_feature_spec(xml)
        assert result.valid is True
        assert any("HUGE" in w for w in result.warnings)

    def test_invalid_priority_warns(self):
        xml = """<feature id="F001" version="1.0" priority="urgent">
            <n>Name</n>
            <description>Desc</description>
            <acceptance_criteria><criterion>C1</criterion></acceptance_criteria>
        </feature>"""
        result = validate_feature_spec(xml)
        assert result.valid is True
        assert any("urgent" in w for w in result.warnings)


class TestDependencyGraphValidation:
    def test_valid_graph_passes(self, sample_dependency_graph):
        result = validate_dependency_graph(sample_dependency_graph)
        assert result.valid is True

    def test_missing_features_key_fails(self):
        result = validate_dependency_graph({"dependencies": {}})
        assert result.valid is False
        assert "features" in result.error

    def test_empty_features_fails(self):
        result = validate_dependency_graph({"features": []})
        assert result.valid is False
        assert "empty" in result.error.lower()

    def test_duplicate_features_fails(self):
        result = validate_dependency_graph({"features": ["F001", "F001"]})
        assert result.valid is False
        assert "duplicate" in result.error.lower()

    def test_dependency_on_missing_feature_fails(self):
        graph = {
            "features": ["F001"],
            "dependencies": {"F001": ["MISSING"]},
        }
        result = validate_dependency_graph(graph)
        assert result.valid is False
        assert "MISSING" in result.error

    def test_self_dependency_fails(self):
        graph = {
            "features": ["F001"],
            "dependencies": {"F001": ["F001"]},
        }
        result = validate_dependency_graph(graph)
        assert result.valid is False
        assert "itself" in result.error

    def test_non_dict_fails(self):
        result = validate_dependency_graph("not a dict")
        assert result.valid is False

    def test_no_dependencies_key_ok(self):
        result = validate_dependency_graph({"features": ["F001"]})
        assert result.valid is True

    def test_non_list_dependencies_fails(self):
        graph = {
            "features": ["F001", "F002"],
            "dependencies": {"F001": "F002"},
        }
        result = validate_dependency_graph(graph)
        assert result.valid is False

    def test_unknown_dependency_key_warns(self):
        graph = {
            "features": ["F001"],
            "dependencies": {"UNKNOWN": ["F001"]},
        }
        result = validate_dependency_graph(graph)
        assert result.valid is True
        assert len(result.warnings) > 0


class TestJournalEntryValidation:
    def test_valid_entry_passes(self):
        entry = {"ts": "2026-03-30T12:00:00Z", "event": "phase_enter", "phase": "analysis"}
        result = validate_journal_entry(entry)
        assert result.valid is True

    def test_missing_ts_fails(self):
        entry = {"event": "phase_enter", "phase": "analysis"}
        result = validate_journal_entry(entry)
        assert result.valid is False
        assert "ts" in result.error

    def test_missing_event_fails(self):
        entry = {"ts": "2026-03-30T12:00:00Z", "phase": "analysis"}
        result = validate_journal_entry(entry)
        assert result.valid is False
        assert "event" in result.error

    def test_missing_phase_fails(self):
        entry = {"ts": "2026-03-30T12:00:00Z", "event": "phase_enter"}
        result = validate_journal_entry(entry)
        assert result.valid is False
        assert "phase" in result.error

    def test_non_dict_fails(self):
        result = validate_journal_entry("not a dict")
        assert result.valid is False

    def test_empty_ts_fails(self):
        entry = {"ts": "", "event": "phase_enter", "phase": "analysis"}
        result = validate_journal_entry(entry)
        assert result.valid is False
