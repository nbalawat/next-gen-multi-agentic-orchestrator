#!/usr/bin/env bash
# Worktree manager: git worktree lifecycle management
# Usage: worktree-manager.sh <command> [args]
# Commands: create, remove, list, status, merge, cleanup
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

exec python3 -c "
from rapids_core.worktree_manager import main
main()
" "$@"
