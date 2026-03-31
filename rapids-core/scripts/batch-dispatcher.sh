#!/usr/bin/env bash
# Batch dispatcher: reads dispatch config from stdin JSON, outputs batch dispatch plan
# Usage: echo '{"wave_number":1,"wave_features":["F001"],"feature_specs":{"F001":"<xml>..."}}' | batch-dispatcher.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

python3 -c "
import sys, json
from rapids_core.batch_dispatcher import create_batch_dispatch_plan

config = json.load(sys.stdin)
plan = create_batch_dispatch_plan(
    wave_number=config['wave_number'],
    wave_features=config['wave_features'],
    feature_specs=config['feature_specs'],
    feature_plugins=config.get('feature_plugins', {}),
    accumulated_context=config.get('accumulated_context'),
    evaluator_template=config.get('evaluator_template', ''),
    project_id=config.get('project_id', ''),
)
json.dump(plan, sys.stdout, indent=2)
print()
"
