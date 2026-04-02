#!/usr/bin/env bash
# SessionStart hook: loads RAPIDS state, shows ASCII banner, and generates CLAUDE.md
# Input (stdin): {"session_id": "...", "source": "startup|resume", "cwd": "..."}
# Hooks must never fail — degrade gracefully, always exit 0

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

# Normalize rapids.json to canonical format (handles flat formats from Claude)
python3 -c "
from rapids_core.config_loader import load_rapids_config, save_rapids_config
config = load_rapids_config('$RAPIDS_DIR')
if config:
    save_rapids_config('$RAPIDS_DIR', config)
" 2>&1 || true

# Display RAPIDS phase banner
python3 -c "
import json
from pathlib import Path
from rapids_core.config_loader import load_rapids_config
from rapids_core.ascii_art import phase_banner
from rapids_core.work_item_manager import migrate_rapids_json, get_active_work_item

config = load_rapids_config('$RAPIDS_DIR')
if not config:
    exit(0)

config = migrate_rapids_json(config)
project_id = config.get('project', {}).get('id', 'unknown')

item = get_active_work_item(config)
if item:
    phase = item['current_phase']
    tier = item['tier']
    phases = item['phases']
    activity = 'Resuming session' if '$SOURCE' == 'resume' else 'Session started'
    activity += f' — Work item {item[\"id\"]}: {item.get(\"title\", \"\")}'
else:
    phase = config.get('current', {}).get('phase', 'unknown')
    tier = config.get('scope', {}).get('tier', 3)
    from rapids_core.phase_router import route_phases
    phases = route_phases(tier)
    activity = 'Resuming session' if '$SOURCE' == 'resume' else 'Session started'

print(phase_banner(
    current_phase=phase,
    activity=activity,
    tier=tier,
    project_name=project_id,
    phases_in_scope=phases,
))
" >&2 || true

# Generate CLAUDE.md
"$PLUGIN_ROOT/scripts/claude-md-generator.sh" "$CWD" >&2 || true

# If resuming, add resumption context
if [ "$SOURCE" = "resume" ]; then
    python3 -c "
import json
from pathlib import Path
from rapids_core.config_loader import load_rapids_config

config = load_rapids_config('$RAPIDS_DIR')
phase = config.get('current', {}).get('phase', 'unknown')
tier = config.get('scope', {}).get('tier', 0)

claude_md = Path('$CWD', 'CLAUDE.md')
if claude_md.exists():
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
" 2>&1 || true
fi

# Log to timeline
python3 -c "
from rapids_core.timeline import log_session_event
log_session_event('$RAPIDS_DIR', 'session_start', user='$SOURCE')
" 2>&1 || true

exit 0
