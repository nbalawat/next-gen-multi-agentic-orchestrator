#!/usr/bin/env bash
# PreCompact hook: archives current context before conversation compaction
# Input (stdin): {"session_id": "...", "cwd": "..."}
set -euo pipefail

INPUT=$(cat)
CWD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd','.'))")

RAPIDS_DIR="$CWD/.rapids"

if [ ! -d "$RAPIDS_DIR" ]; then
    exit 0
fi

# Save current state to accumulated context
python3 -c "
import json, datetime
from pathlib import Path

rapids_dir = Path('$RAPIDS_DIR')
rapids_json_path = rapids_dir / 'rapids.json'
context_path = rapids_dir / 'context' / 'accumulated.json'

if not rapids_json_path.is_file():
    exit(0)

rapids_json = json.loads(rapids_json_path.read_text())

# Load existing accumulated context or create new
if context_path.is_file():
    context = json.loads(context_path.read_text())
else:
    context = {}

# Update with current state snapshot
context['last_compacted'] = datetime.datetime.utcnow().isoformat() + 'Z'
context['current_phase'] = rapids_json.get('current', {}).get('phase', '')
context['tier'] = rapids_json.get('scope', {}).get('tier', 0)

# Preserve key decisions and constraints
if 'key_decisions' not in context:
    context['key_decisions'] = []
if 'constraints' not in context:
    context['constraints'] = []

context_path.write_text(json.dumps(context, indent=2))
" 2>&1

# Regenerate CLAUDE.md with fresh context
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
"$PLUGIN_ROOT/scripts/claude-md-generator.sh" "$CWD" 2>&1

exit 0
