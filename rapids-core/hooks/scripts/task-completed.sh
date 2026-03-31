#!/usr/bin/env bash
# TaskCompleted hook: updates feature progress and dependency graph
# Input (stdin): {"session_id": "...", "task_id": "...", "cwd": "..."}
set -euo pipefail

INPUT=$(cat)
CWD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd','.'))")

RAPIDS_DIR="$CWD/.rapids"

if [ ! -d "$RAPIDS_DIR" ]; then
    exit 0
fi

# Log task completion to timeline
python3 -c "
import json, datetime
from pathlib import Path

input_data = json.loads('''$INPUT''')
rapids_dir = Path('$RAPIDS_DIR')

rapids_json_path = rapids_dir / 'rapids.json'
if not rapids_json_path.is_file():
    exit(0)

rapids_json = json.loads(rapids_json_path.read_text())
phase = rapids_json.get('current', {}).get('phase', 'unknown')

entry = {
    'ts': datetime.datetime.utcnow().isoformat() + 'Z',
    'event': 'task_completed',
    'phase': phase,
    'details': {
        'task_id': input_data.get('task_id', ''),
    }
}

timeline_file = rapids_dir / 'audit' / 'timeline.jsonl'
with open(timeline_file, 'a') as f:
    f.write(json.dumps(entry) + '\n')
" 2>&1

exit 0
