#!/usr/bin/env bash
# Stop hook: validates required phase artifacts exist before allowing phase exit
# Input (stdin): {"session_id": "...", "stop_hook_active": false, "cwd": "..."}
# Exit codes: 0 = allow stop, 2 = block stop with feedback
# Hooks must never fail — degrade gracefully, always exit 0

INPUT=$(cat)
CWD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd','.'))")

RAPIDS_DIR="$CWD/.rapids"

# Only act if this is a RAPIDS project
if [ ! -d "$RAPIDS_DIR" ]; then
    exit 0
fi

if [ ! -f "$RAPIDS_DIR/rapids.json" ]; then
    exit 0
fi

# Check required artifacts for current phase
python3 -c "
import json, sys
from pathlib import Path

rapids_dir = Path('$RAPIDS_DIR')
rapids_json = json.loads((rapids_dir / 'rapids.json').read_text())
phase = rapids_json.get('current', {}).get('phase', '')

# Define required artifacts per phase
required = {
    'research': ['phases/research/problem-statement.md'],
    'analysis': ['phases/analysis/solution-design.md'],
    'plan': ['phases/plan/features'],  # Directory with feature specs
    'implement': [],  # Checked via feature-progress files
    'deploy': [],
    'sustain': [],
}

missing = []
for artifact in required.get(phase, []):
    artifact_path = rapids_dir / artifact
    if not artifact_path.exists():
        missing.append(artifact)

if missing:
    feedback = 'Cannot exit {} phase. Missing required artifacts:\n'.format(phase)
    for m in missing:
        feedback += f'  - {m}\n'
    feedback += '\nPlease create these artifacts before stopping.'
    print(feedback)
    sys.exit(2)

sys.exit(0)
" 2>&1 || exit $?
