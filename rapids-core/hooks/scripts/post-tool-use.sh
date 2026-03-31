#!/usr/bin/env bash
# PostToolUse hook: logs cost entries and validates artifacts on write
# Input (stdin): {"session_id": "...", "tool_name": "...", "tool_input": {...}, "cwd": "..."}
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

INPUT=$(cat)
CWD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd','.'))")

RAPIDS_DIR="$CWD/.rapids"

# Only act if this is a RAPIDS project
if [ ! -d "$RAPIDS_DIR" ]; then
    exit 0
fi

# Log cost entry
python3 -c "
import json, datetime, sys
from pathlib import Path

input_data = json.loads('''$INPUT''')
rapids_dir = Path('$RAPIDS_DIR')

# Read current phase
rapids_json_path = rapids_dir / 'rapids.json'
if rapids_json_path.is_file():
    rapids_json = json.loads(rapids_json_path.read_text())
    phase = rapids_json.get('current', {}).get('phase', 'unknown')
else:
    phase = 'unknown'

# Append cost entry (tokens are estimated; real values come from API)
entry = {
    'ts': datetime.datetime.utcnow().isoformat() + 'Z',
    'phase': phase,
    'tool_name': input_data.get('tool_name', ''),
    'model': '',
    'input_tokens': 0,
    'output_tokens': 0,
    'cost_usd': 0.0,
}
cost_file = rapids_dir / 'audit' / 'cost.jsonl'
with open(cost_file, 'a') as f:
    f.write(json.dumps(entry) + '\n')

# Log to timeline
timeline_entry = {
    'ts': entry['ts'],
    'event': 'tool_use',
    'phase': phase,
    'details': {
        'tool': input_data.get('tool_name', ''),
    }
}
timeline_file = rapids_dir / 'audit' / 'timeline.jsonl'
with open(timeline_file, 'a') as f:
    f.write(json.dumps(timeline_entry) + '\n')

# If a Write tool created a .rapids/ artifact, validate it
tool_name = input_data.get('tool_name', '')
tool_input = input_data.get('tool_input', {})
if tool_name == 'Write':
    file_path = tool_input.get('file_path', tool_input.get('path', ''))
    if '.rapids/' in file_path and (file_path.endswith('.xml') or file_path.endswith('.json')):
        # Trigger validation (non-blocking)
        import subprocess
        result = subprocess.run(
            ['$PLUGIN_ROOT/scripts/artifact-validator.sh', file_path],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            validation = json.loads(result.stdout)
            if not validation.get('valid', True):
                print(f'Artifact validation warning: {validation.get(\"error\", \"\")}', file=sys.stderr)
" 2>&1

exit 0
