#!/usr/bin/env bash
# Agent team orchestrator: reads config from stdin JSON, outputs agent team plan
# Usage: echo '{"wave_number":1,"wave_features":["F001"],"feature_specs":{...},...}' | agent-team-orchestrator.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

python3 -c "
import sys, json
from rapids_core.agent_team_orchestrator import create_agent_team_plan

config = json.load(sys.stdin)
plan = create_agent_team_plan(
    wave_number=config['wave_number'],
    wave_features=config['wave_features'],
    feature_specs=config['feature_specs'],
    feature_plugins=config.get('feature_plugins', {}),
    available_agents=config.get('available_agents', []),
    dependency_graph=config.get('dependency_graph'),
    accumulated_context=config.get('accumulated_context'),
    evaluator_template=config.get('evaluator_template', ''),
    project_id=config.get('project_id', ''),
    max_retries=config.get('max_retries', 3),
)
json.dump(plan, sys.stdout, indent=2)
print()
"
