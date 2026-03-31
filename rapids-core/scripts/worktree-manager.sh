#!/usr/bin/env bash
# Worktree manager: git worktree lifecycle management
# Usage: worktree-manager.sh <command> [args]
# Commands: create, remove, list, status, merge, cleanup
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

python3 -c "
import sys
sys.argv = $(python3 -c "import sys,json; print(json.dumps(sys.argv))" "$0" "$@")
from rapids_core.worktree_manager import main
main()
" "$@"
