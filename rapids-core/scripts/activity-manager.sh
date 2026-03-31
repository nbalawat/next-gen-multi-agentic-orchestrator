#!/usr/bin/env bash
# Activity manager: manages phase activities and progress tracking
# Usage: activity-manager.sh <command> [args]
# Commands: load, waves, init-progress, update, check-gate, checklist
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

python3 -c "
import sys, json
from rapids_core.activity_manager import (
    load_phase_activities, compute_activity_waves,
    initialize_activity_progress, update_activity_status,
    check_phase_gate, format_activity_checklist,
    read_activity_progress,
)

command = sys.argv[1] if len(sys.argv) > 1 else ''
activities_dir = '$PLUGIN_ROOT/activities'

if command == 'load':
    phase = sys.argv[2] if len(sys.argv) > 2 else 'research'
    acts = load_phase_activities(phase, activities_dir=activities_dir)
    print(json.dumps(acts, indent=2))

elif command == 'waves':
    phase = sys.argv[2] if len(sys.argv) > 2 else 'research'
    acts = load_phase_activities(phase, activities_dir=activities_dir)
    waves = compute_activity_waves(acts)
    for i, wave in enumerate(waves, 1):
        print(f'Wave {i}: {wave}')

elif command == 'init-progress':
    data = json.loads(sys.stdin.read())
    acts = load_phase_activities(data['phase'], activities_dir=activities_dir)
    progress = initialize_activity_progress(data['phase'], acts, data['output_dir'])
    print(json.dumps(progress, indent=2))

elif command == 'update':
    data = json.loads(sys.stdin.read())
    progress = update_activity_status(
        data['progress_file'], data['activity_id'],
        data['status'], data.get('outputs'),
    )
    print(json.dumps(progress, indent=2))

elif command == 'check-gate':
    pf = sys.argv[2] if len(sys.argv) > 2 else ''
    result = check_phase_gate(pf)
    print(json.dumps({'gate_passed': result}))

elif command == 'checklist':
    phase = sys.argv[2] if len(sys.argv) > 2 else 'research'
    pf = sys.argv[3] if len(sys.argv) > 3 else None
    acts = load_phase_activities(phase, activities_dir=activities_dir)
    progress = read_activity_progress(pf) if pf else None
    print(format_activity_checklist(acts, progress))

else:
    print('Usage: activity-manager.sh <load|waves|init-progress|update|check-gate|checklist> [args]', file=sys.stderr)
    sys.exit(1)
" "$@"
