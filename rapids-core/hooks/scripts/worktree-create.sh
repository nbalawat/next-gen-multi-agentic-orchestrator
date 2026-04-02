#!/usr/bin/env bash
# WorktreeCreate hook: sets up RAPIDS context in a new worktree
# Input (stdin): {"session_id": "...", "worktree_path": "...", "cwd": "..."}
#
# This hook MUST NOT fail — exit 0 always. Errors are logged but don't block
# worktree creation. Use || true after every command that could fail.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Read all of stdin once into a variable
INPUT=$(cat)

# Parse fields from the JSON input
CWD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd','.'))" 2>/dev/null || echo ".")
WORKTREE=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('worktree_path',''))" 2>/dev/null || echo "")

RAPIDS_DIR="$CWD/.rapids"

# Only act if this is a RAPIDS project
if [ ! -d "$RAPIDS_DIR" ]; then
    exit 0
fi

if [ -z "$WORKTREE" ]; then
    exit 0
fi

# Create .rapids/ structure in the worktree with essential state
python3 -c "
import json, shutil
from pathlib import Path

cwd = '$CWD'
worktree = '$WORKTREE'
rapids_dir = Path(cwd) / '.rapids'
worktree_rapids = Path(worktree) / '.rapids'

# Create minimal .rapids/ in worktree
worktree_rapids.mkdir(exist_ok=True)
(worktree_rapids / 'audit').mkdir(exist_ok=True)
(worktree_rapids / 'context').mkdir(exist_ok=True)
(worktree_rapids / 'phases').mkdir(exist_ok=True)

# Copy rapids.json
src = rapids_dir / 'rapids.json'
if src.is_file():
    shutil.copy2(src, worktree_rapids / 'rapids.json')

# Copy accumulated context
context_src = rapids_dir / 'context' / 'accumulated.json'
if context_src.is_file():
    shutil.copy2(context_src, worktree_rapids / 'context' / 'accumulated.json')

# Create empty audit files for the worktree
(worktree_rapids / 'audit' / 'cost.jsonl').touch()
(worktree_rapids / 'audit' / 'timeline.jsonl').touch()

print('RAPIDS worktree state initialized')
" 2>/dev/null || true

# Generate CLAUDE.md in worktree (non-blocking)
"$PLUGIN_ROOT/scripts/claude-md-generator.sh" "$WORKTREE" 2>/dev/null || true

exit 0
