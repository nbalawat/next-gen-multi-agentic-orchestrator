"""F1 tests for cost tracker. Zero LLM calls."""

import json

import pytest

from rapids_core.cost_tracker import append_cost_entry, aggregate_costs
from rapids_core.models import CostEntry


class TestAppendCostEntry:
    def test_appends_entry(self, tmp_path):
        jsonl = tmp_path / "cost.jsonl"
        jsonl.touch()
        entry = CostEntry(
            ts="2026-03-30T12:00:00Z",
            phase="analysis",
            feature="F001",
            model="opus",
            input_tokens=1000,
            output_tokens=500,
            cost_usd=0.15,
        )
        append_cost_entry(jsonl, entry)
        lines = jsonl.read_text().strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["phase"] == "analysis"
        assert data["cost_usd"] == 0.15

    def test_appends_multiple_entries(self, tmp_path):
        jsonl = tmp_path / "cost.jsonl"
        jsonl.touch()
        for i in range(3):
            entry = CostEntry(
                ts=f"2026-03-30T12:0{i}:00Z",
                phase="implement",
                cost_usd=0.10 * (i + 1),
            )
            append_cost_entry(jsonl, entry)
        lines = jsonl.read_text().strip().splitlines()
        assert len(lines) == 3


class TestAggregateCosts:
    def test_empty_file(self, tmp_path):
        jsonl = tmp_path / "cost.jsonl"
        jsonl.touch()
        result = aggregate_costs(jsonl)
        assert result.total_cost == 0.0
        assert result.entry_count == 0

    def test_missing_file(self, tmp_path):
        result = aggregate_costs(tmp_path / "nonexistent.jsonl")
        assert result.total_cost == 0.0
        assert result.entry_count == 0

    def test_single_entry(self, tmp_path):
        jsonl = tmp_path / "cost.jsonl"
        jsonl.write_text(
            json.dumps({
                "ts": "2026-03-30T12:00:00Z",
                "phase": "analysis",
                "feature": "F001",
                "model": "opus",
                "input_tokens": 1000,
                "output_tokens": 500,
                "cost_usd": 0.15,
            })
            + "\n"
        )
        result = aggregate_costs(jsonl)
        assert result.total_cost == 0.15
        assert result.total_input_tokens == 1000
        assert result.total_output_tokens == 500
        assert result.entry_count == 1
        assert result.by_phase == {"analysis": 0.15}
        assert result.by_feature == {"F001": 0.15}
        assert result.by_model == {"opus": 0.15}

    def test_multi_phase_aggregation(self, tmp_path):
        jsonl = tmp_path / "cost.jsonl"
        entries = [
            {"ts": "t1", "phase": "analysis", "model": "opus", "cost_usd": 1.00,
             "feature": "F001", "input_tokens": 100, "output_tokens": 50},
            {"ts": "t2", "phase": "plan", "model": "sonnet", "cost_usd": 0.50,
             "feature": "F001", "input_tokens": 200, "output_tokens": 100},
            {"ts": "t3", "phase": "implement", "model": "sonnet", "cost_usd": 0.30,
             "feature": "F002", "input_tokens": 150, "output_tokens": 75},
        ]
        jsonl.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
        result = aggregate_costs(jsonl)
        assert result.total_cost == pytest.approx(1.80, abs=0.01)
        assert result.by_phase["analysis"] == 1.00
        assert result.by_phase["plan"] == 0.50
        assert result.by_model["opus"] == 1.00
        assert result.by_model["sonnet"] == pytest.approx(0.80, abs=0.01)
        assert result.entry_count == 3

    def test_malformed_lines_skipped(self, tmp_path):
        jsonl = tmp_path / "cost.jsonl"
        jsonl.write_text(
            'not json\n'
            + json.dumps({"ts": "t1", "phase": "analysis", "model": "opus", "cost_usd": 0.50})
            + "\n"
            + "also bad\n"
        )
        result = aggregate_costs(jsonl)
        assert result.total_cost == 0.50
        assert result.entry_count == 1

    def test_blank_lines_skipped(self, tmp_path):
        jsonl = tmp_path / "cost.jsonl"
        jsonl.write_text(
            "\n\n"
            + json.dumps({"ts": "t1", "phase": "analysis", "model": "opus", "cost_usd": 0.25})
            + "\n\n"
        )
        result = aggregate_costs(jsonl)
        assert result.entry_count == 1

    def test_missing_feature_not_in_by_feature(self, tmp_path):
        jsonl = tmp_path / "cost.jsonl"
        jsonl.write_text(
            json.dumps({"ts": "t1", "phase": "analysis", "model": "opus",
                         "cost_usd": 0.10, "feature": ""})
            + "\n"
        )
        result = aggregate_costs(jsonl)
        assert result.by_feature == {}
