#!/usr/bin/env bash
# SessionStart hook: loads RAPIDS state and generates CLAUDE.md
# Input (stdin): {"session_id": "...", "source": "startup|resume", "cwd": "..."}
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Read hook input
INPUT=$(cat)
CWD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd','.'))")
SOURCE=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('source','startup'))")

RAPIDS_DIR="$CWD/.rapids"

# Only act if this is a RAPIDS project
if [ ! -d "$RAPIDS_DIR" ]; then
    exit 0
fi

if [ ! -f "$RAPIDS_DIR/rapids.json" ]; then
    exit 0
fi

# Generate CLAUDE.md
"$PLUGIN_ROOT/scripts/claude-md-generator.sh" "$CWD" >&2

# If resuming, add resumption context
if [ "$SOURCE" = "resume" ]; then
    python3 -c "
import json
from pathlib import Path

cwd = '$CWD'
rapids_json = json.loads(Path(cwd, '.rapids', 'rapids.json').read_text())
phase = rapids_json.get('current', {}).get('phase', 'unknown')
tier = rapids_json.get('scope', {}).get('tier', 0)

# Read current CLAUDE.md and prepend welcome back message
claude_md = Path(cwd, 'CLAUDE.md')
content = claude_md.read_text()
resume_msg = f'''
## Welcome Back

Resuming RAPIDS session. Current state:
- **Phase:** {phase}
- **Tier:** {tier}

Review .rapids/rapids.json for full state.

---

'''
claude_md.write_text(resume_msg + content)
" 2>&1
fi

# Log to timeline
python3 -c "
import json, datetime
from pathlib import Path

entry = {
    'ts': datetime.datetime.utcnow().isoformat() + 'Z',
    'event': 'session_start',
    'phase': json.loads(Path('$RAPIDS_DIR/rapids.json').read_text()).get('current',{}).get('phase','unknown'),
    'details': {'source': '$SOURCE'}
}
with open('$RAPIDS_DIR/audit/timeline.jsonl', 'a') as f:
    f.write(json.dumps(entry) + '\n')
" 2>&1

exit 0
