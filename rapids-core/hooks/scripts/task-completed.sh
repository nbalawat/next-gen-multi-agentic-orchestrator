#!/usr/bin/env bash
# TaskCompleted hook: logs task completion to timeline
# Input (stdin): {"session_id": "...", "task_id": "...", "cwd": "..."}
set -euo pipefail

INPUT=$(cat)
CWD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd','.'))")

RAPIDS_DIR="$CWD/.rapids"

if [ ! -d "$RAPIDS_DIR" ]; then
    exit 0
fi

python3 -c "
import json
from rapids_core.config_loader import load_rapids_config
from rapids_core.timeline import log_event

input_data = json.loads('''$INPUT''')
config = load_rapids_config('$RAPIDS_DIR')
phase = config.get('current', {}).get('phase', 'unknown')

log_event(
    '$RAPIDS_DIR',
    event='task_completed',
    phase=phase,
    details={'task_id': input_data.get('task_id', '')},
)
" 2>&1

exit 0
