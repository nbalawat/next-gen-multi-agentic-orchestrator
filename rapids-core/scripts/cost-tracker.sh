#!/usr/bin/env bash
# Cost tracker: reads cost.jsonl and outputs aggregated summary
# Usage: cost-tracker.sh [path-to-cost.jsonl]
set -euo pipefail

COST_FILE="${1:-.rapids/audit/cost.jsonl}"

python3 -c "
import sys, json
from rapids_core.cost_tracker import aggregate_costs

summary = aggregate_costs('$COST_FILE')
json.dump({
    'total_cost': summary.total_cost,
    'total_input_tokens': summary.total_input_tokens,
    'total_output_tokens': summary.total_output_tokens,
    'by_phase': summary.by_phase,
    'by_feature': summary.by_feature,
    'by_model': summary.by_model,
    'entry_count': summary.entry_count,
}, sys.stdout, indent=2)
print()
"
