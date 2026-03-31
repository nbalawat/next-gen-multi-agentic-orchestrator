"""F1 tests for feature progress tracking. Zero LLM calls."""

import json
import pytest
from pathlib import Path

from rapids_core.feature_progress import (
    initialize_feature_progress,
    read_feature_progress,
    update_feature_status,
    aggregate_wave_progress,
    is_wave_complete,
)


def _make_spec(fid: str = "F001", criteria: list[str] | None = None) -> str:
    if criteria is None:
        criteria = ["Criterion 1", "Criterion 2", "Criterion 3"]
    criteria_xml = "\n".join(f"        <criterion>{c}</criterion>" for c in criteria)
    return f"""<feature id="{fid}" version="1.0" priority="high" depends_on="" plugin="">
    <n>Feature {fid}</n>
    <description>Description of {fid}</description>
    <acceptance_criteria>
{criteria_xml}
    </acceptance_criteria>
    <estimated_complexity>M</estimated_complexity>
</feature>"""


class TestInitializeFeatureProgress:
    def test_creates_progress_file(self, tmp_path):
        progress = initialize_feature_progress("F001", _make_spec("F001"), str(tmp_path))
        assert (tmp_path / "feature-progress-F001.json").exists()

    def test_status_is_not_started(self, tmp_path):
        progress = initialize_feature_progress("F001", _make_spec("F001"), str(tmp_path))
        assert progress["status"] == "not_started"

    def test_extracts_acceptance_criteria(self, tmp_path):
        progress = initialize_feature_progress("F001", _make_spec("F001"), str(tmp_path))
        assert len(progress["acceptance_criteria"]) == 3
        assert progress["acceptance_criteria"][0]["criterion"] == "Criterion 1"
        assert progress["acceptance_criteria"][0]["status"] == "pending"

    def test_criteria_have_empty_tests_and_commits(self, tmp_path):
        progress = initialize_feature_progress("F001", _make_spec("F001"), str(tmp_path))
        for c in progress["acceptance_criteria"]:
            assert c["tests"] == []
            assert c["commits"] == []

    def test_timestamps_are_null(self, tmp_path):
        progress = initialize_feature_progress("F001", _make_spec("F001"), str(tmp_path))
        assert progress["started_at"] is None
        assert progress["completed_at"] is None

    def test_evaluator_verdict_is_null(self, tmp_path):
        progress = initialize_feature_progress("F001", _make_spec("F001"), str(tmp_path))
        assert progress["evaluator_verdict"] is None

    def test_retry_count_is_zero(self, tmp_path):
        progress = initialize_feature_progress("F001", _make_spec("F001"), str(tmp_path))
        assert progress["retry_count"] == 0

    def test_creates_output_dir_if_missing(self, tmp_path):
        nested = tmp_path / "deep" / "nested" / "dir"
        initialize_feature_progress("F001", _make_spec("F001"), str(nested))
        assert nested.is_dir()

    def test_malformed_xml_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Cannot parse"):
            initialize_feature_progress("F001", "<not valid", str(tmp_path))

    def test_no_criteria_raises(self, tmp_path):
        xml = """<feature id="F001" version="1.0" priority="high">
            <n>Test</n><description>D</description>
        </feature>"""
        with pytest.raises(ValueError, match="no acceptance_criteria"):
            initialize_feature_progress("F001", xml, str(tmp_path))

    def test_custom_criteria_count(self, tmp_path):
        progress = initialize_feature_progress(
            "F001", _make_spec("F001", ["A", "B", "C", "D", "E"]), str(tmp_path)
        )
        assert len(progress["acceptance_criteria"]) == 5


class TestReadFeatureProgress:
    def test_reads_initialized_progress(self, tmp_path):
        initialize_feature_progress("F001", _make_spec("F001"), str(tmp_path))
        progress = read_feature_progress(str(tmp_path / "feature-progress-F001.json"))
        assert progress["feature_id"] == "F001"

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            read_feature_progress("/tmp/nonexistent-progress-12345.json")


class TestUpdateFeatureStatus:
    def test_update_overall_status(self, tmp_path):
        initialize_feature_progress("F001", _make_spec("F001"), str(tmp_path))
        pf = str(tmp_path / "feature-progress-F001.json")
        updated = update_feature_status(pf, status="in_progress")
        assert updated["status"] == "in_progress"
        assert updated["started_at"] is not None

    def test_update_criterion_status(self, tmp_path):
        initialize_feature_progress("F001", _make_spec("F001"), str(tmp_path))
        pf = str(tmp_path / "feature-progress-F001.json")
        updated = update_feature_status(pf, criterion_index=0, criterion_status="complete")
        assert updated["acceptance_criteria"][0]["status"] == "complete"

    def test_add_test_name(self, tmp_path):
        initialize_feature_progress("F001", _make_spec("F001"), str(tmp_path))
        pf = str(tmp_path / "feature-progress-F001.json")
        updated = update_feature_status(pf, criterion_index=0, test_name="test_criterion_1")
        assert "test_criterion_1" in updated["acceptance_criteria"][0]["tests"]

    def test_add_commit_hash(self, tmp_path):
        initialize_feature_progress("F001", _make_spec("F001"), str(tmp_path))
        pf = str(tmp_path / "feature-progress-F001.json")
        updated = update_feature_status(pf, criterion_index=0, commit_hash="abc1234")
        assert "abc1234" in updated["acceptance_criteria"][0]["commits"]

    def test_set_evaluator_verdict(self, tmp_path):
        initialize_feature_progress("F001", _make_spec("F001"), str(tmp_path))
        pf = str(tmp_path / "feature-progress-F001.json")
        updated = update_feature_status(pf, evaluator_verdict="pass")
        assert updated["evaluator_verdict"] == "pass"

    def test_increment_retry(self, tmp_path):
        initialize_feature_progress("F001", _make_spec("F001"), str(tmp_path))
        pf = str(tmp_path / "feature-progress-F001.json")
        update_feature_status(pf, increment_retry=True)
        updated = update_feature_status(pf, increment_retry=True)
        assert updated["retry_count"] == 2

    def test_complete_sets_timestamp(self, tmp_path):
        initialize_feature_progress("F001", _make_spec("F001"), str(tmp_path))
        pf = str(tmp_path / "feature-progress-F001.json")
        updated = update_feature_status(pf, status="complete")
        assert updated["completed_at"] is not None

    def test_persists_to_file(self, tmp_path):
        initialize_feature_progress("F001", _make_spec("F001"), str(tmp_path))
        pf = str(tmp_path / "feature-progress-F001.json")
        update_feature_status(pf, status="in_progress")
        # Re-read from file
        reread = read_feature_progress(pf)
        assert reread["status"] == "in_progress"


class TestAggregateWaveProgress:
    def test_all_not_started(self, tmp_path):
        result = aggregate_wave_progress(str(tmp_path), ["F001", "F002"])
        assert result["total_features"] == 2
        assert result["not_started"] == 2

    def test_mixed_progress(self, tmp_path):
        initialize_feature_progress("F001", _make_spec("F001"), str(tmp_path))
        initialize_feature_progress("F002", _make_spec("F002"), str(tmp_path))
        pf1 = str(tmp_path / "feature-progress-F001.json")
        update_feature_status(pf1, status="complete", evaluator_verdict="pass")
        pf2 = str(tmp_path / "feature-progress-F002.json")
        update_feature_status(pf2, status="in_progress")

        result = aggregate_wave_progress(str(tmp_path), ["F001", "F002"])
        assert result["complete"] == 1
        assert result["in_progress"] == 1

    def test_failed_feature_counted(self, tmp_path):
        initialize_feature_progress("F001", _make_spec("F001"), str(tmp_path))
        pf = str(tmp_path / "feature-progress-F001.json")
        update_feature_status(pf, status="in_progress", evaluator_verdict="fail")

        result = aggregate_wave_progress(str(tmp_path), ["F001"])
        assert result["failed"] == 1

    def test_per_feature_criteria_counts(self, tmp_path):
        initialize_feature_progress("F001", _make_spec("F001"), str(tmp_path))
        pf = str(tmp_path / "feature-progress-F001.json")
        update_feature_status(pf, status="in_progress", criterion_index=0, criterion_status="complete")

        result = aggregate_wave_progress(str(tmp_path), ["F001"])
        assert result["features"]["F001"]["criteria_done"] == 1
        assert result["features"]["F001"]["criteria_total"] == 3


class TestIsWaveComplete:
    def test_incomplete_wave(self, tmp_path):
        initialize_feature_progress("F001", _make_spec("F001"), str(tmp_path))
        assert is_wave_complete(str(tmp_path), ["F001"]) is False

    def test_complete_wave(self, tmp_path):
        initialize_feature_progress("F001", _make_spec("F001"), str(tmp_path))
        pf = str(tmp_path / "feature-progress-F001.json")
        update_feature_status(pf, status="complete", evaluator_verdict="pass")
        assert is_wave_complete(str(tmp_path), ["F001"]) is True

    def test_complete_but_failed_verdict(self, tmp_path):
        initialize_feature_progress("F001", _make_spec("F001"), str(tmp_path))
        pf = str(tmp_path / "feature-progress-F001.json")
        update_feature_status(pf, status="complete", evaluator_verdict="fail")
        assert is_wave_complete(str(tmp_path), ["F001"]) is False

    def test_missing_progress_file(self, tmp_path):
        assert is_wave_complete(str(tmp_path), ["F001"]) is False

    def test_all_features_must_be_complete(self, tmp_path):
        initialize_feature_progress("F001", _make_spec("F001"), str(tmp_path))
        initialize_feature_progress("F002", _make_spec("F002"), str(tmp_path))
        pf1 = str(tmp_path / "feature-progress-F001.json")
        update_feature_status(pf1, status="complete", evaluator_verdict="pass")
        # F002 still not started
        assert is_wave_complete(str(tmp_path), ["F001", "F002"]) is False
