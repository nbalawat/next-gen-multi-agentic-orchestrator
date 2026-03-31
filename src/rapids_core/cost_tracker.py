"""Cost tracking: reads/writes cost JSONL logs and aggregates costs."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from rapids_core.models import CostEntry, CostSummary


def append_cost_entry(jsonl_path: str | Path, entry: CostEntry) -> None:
    """Append a cost entry to a JSONL file.

    Args:
        jsonl_path: Path to the cost.jsonl file.
        entry: CostEntry to append.
    """
    line = json.dumps(
        {
            "ts": entry.ts,
            "phase": entry.phase,
            "feature": entry.feature,
            "model": entry.model,
            "input_tokens": entry.input_tokens,
            "output_tokens": entry.output_tokens,
            "cost_usd": entry.cost_usd,
        }
    )
    with open(jsonl_path, "a") as f:
        f.write(line + "\n")


def aggregate_costs(jsonl_path: str | Path) -> CostSummary:
    """Aggregate costs from a JSONL file.

    Handles malformed lines gracefully by skipping them.

    Args:
        jsonl_path: Path to the cost.jsonl file.

    Returns:
        CostSummary with totals and per-phase/feature/model breakdowns.
    """
    path = Path(jsonl_path)

    by_phase: dict[str, float] = defaultdict(float)
    by_feature: dict[str, float] = defaultdict(float)
    by_model: dict[str, float] = defaultdict(float)
    total_cost = 0.0
    total_input = 0
    total_output = 0
    entry_count = 0

    if not path.is_file():
        return CostSummary(
            total_cost=0.0,
            total_input_tokens=0,
            total_output_tokens=0,
            entry_count=0,
        )

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue

        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue  # Skip malformed lines

        cost = data.get("cost_usd", 0.0)
        total_cost += cost
        total_input += data.get("input_tokens", 0)
        total_output += data.get("output_tokens", 0)
        entry_count += 1

        phase = data.get("phase", "unknown")
        by_phase[phase] += cost

        feature = data.get("feature", "")
        if feature:
            by_feature[feature] += cost

        model = data.get("model", "unknown")
        by_model[model] += cost

    return CostSummary(
        total_cost=round(total_cost, 4),
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        by_phase=dict(by_phase),
        by_feature=dict(by_feature),
        by_model=dict(by_model),
        entry_count=entry_count,
    )
