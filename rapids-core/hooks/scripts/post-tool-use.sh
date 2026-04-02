#!/usr/bin/env bash
# PostToolUse hook: logs cost entries, timeline events, and validates artifacts on write
# Input (stdin): {"session_id": "...", "tool_name": "...", "tool_input": {...}, "cwd": "..."}
# Hooks must never fail — degrade gracefully, always exit 0

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

INPUT=$(cat)
CWD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd','.'))")

RAPIDS_DIR="$CWD/.rapids"

# Only act if this is a RAPIDS project
if [ ! -d "$RAPIDS_DIR" ]; then
    exit 0
fi

python3 -c "
import json, datetime, sys, os
from pathlib import Path

input_data = json.loads('''$INPUT''')
rapids_dir = Path('$RAPIDS_DIR')

# Read current phase using config loader (handles any format)
try:
    from rapids_core.config_loader import load_rapids_config
    config = load_rapids_config(str(rapids_dir))
    phase = config.get('current', {}).get('phase', 'unknown')
except Exception:
    phase = 'unknown'

ts = datetime.datetime.utcnow().isoformat() + 'Z'
tool_name = input_data.get('tool_name', '')

# Append cost entry
cost_entry = {
    'ts': ts,
    'phase': phase,
    'tool_name': tool_name,
    'model': '',
    'input_tokens': 0,
    'output_tokens': 0,
    'cost_usd': 0.0,
}
cost_file = rapids_dir / 'audit' / 'cost.jsonl'
cost_file.parent.mkdir(parents=True, exist_ok=True)
with open(cost_file, 'a') as f:
    f.write(json.dumps(cost_entry) + '\n')

# Log tool use to timeline
from rapids_core.timeline import log_event
log_event(str(rapids_dir), 'tool_use', phase=phase, details={'tool': tool_name})

# If Write/Edit touches .rapids/phases/, log artifact event
tool_input = input_data.get('tool_input', {})
if tool_name in ('Write', 'Edit'):
    file_path = tool_input.get('file_path', tool_input.get('path', ''))
    if '.rapids/phases/' in file_path:
        artifact_name = os.path.basename(file_path)
        # Determine phase from path
        parts = file_path.split('.rapids/phases/')
        artifact_phase = parts[1].split('/')[0] if len(parts) > 1 else phase
        from rapids_core.timeline import log_artifact_created
        log_artifact_created(str(rapids_dir), artifact_name, artifact_phase)

# Validate artifacts on write
if tool_name == 'Write':
    file_path = tool_input.get('file_path', tool_input.get('path', ''))
    if '.rapids/' in file_path and (file_path.endswith('.xml') or file_path.endswith('.json')):
        import subprocess
        result = subprocess.run(
            ['$PLUGIN_ROOT/scripts/artifact-validator.sh', file_path],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            try:
                validation = json.loads(result.stdout)
                if not validation.get('valid', True):
                    print(f'Artifact validation warning: {validation.get(\"error\", \"\")}', file=sys.stderr)
            except json.JSONDecodeError:
                pass
" 2>&1

exit 0
