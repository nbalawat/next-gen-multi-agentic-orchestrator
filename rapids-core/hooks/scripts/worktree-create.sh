#!/usr/bin/env bash
# WorktreeCreate hook: sets up RAPIDS context in a new worktree
# Input (stdin): {"session_id": "...", "worktree_path": "...", "cwd": "..."}
set -euo pipefail

INPUT=$(cat)
CWD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd','.'))")
WORKTREE=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('worktree_path',''))")

RAPIDS_DIR="$CWD/.rapids"

if [ ! -d "$RAPIDS_DIR" ]; then
    exit 0
fi

if [ -z "$WORKTREE" ]; then
    exit 0
fi

# Create .rapids symlink or copy essential state into the worktree
python3 -c "
import json, os, shutil
from pathlib import Path

cwd = '$CWD'
worktree = '$WORKTREE'
rapids_dir = Path(cwd) / '.rapids'
worktree_rapids = Path(worktree) / '.rapids'

# Create minimal .rapids/ in worktree with symlinks to shared state
worktree_rapids.mkdir(exist_ok=True)
(worktree_rapids / 'audit').mkdir(exist_ok=True)
(worktree_rapids / 'context').mkdir(exist_ok=True)

# Copy rapids.json (each worktree may need to track its own feature)
shutil.copy2(rapids_dir / 'rapids.json', worktree_rapids / 'rapids.json')

# Copy accumulated context
context_src = rapids_dir / 'context' / 'accumulated.json'
if context_src.is_file():
    shutil.copy2(context_src, worktree_rapids / 'context' / 'accumulated.json')

# Create empty audit files for the worktree
(worktree_rapids / 'audit' / 'cost.jsonl').touch()
(worktree_rapids / 'audit' / 'timeline.jsonl').touch()
" 2>&1

# Generate CLAUDE.md in worktree
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
"$PLUGIN_ROOT/scripts/claude-md-generator.sh" "$WORKTREE" 2>&1

exit 0
