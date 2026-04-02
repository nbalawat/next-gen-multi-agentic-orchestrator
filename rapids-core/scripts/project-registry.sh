#!/usr/bin/env bash
# Project registry wrapper: manages tracked RAPIDS projects
# Usage: project-registry.sh <command> [args]
# Commands: list, register, update-phase, deactivate, get,
#           register-workspace, list-workspaces, workspace-projects
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

exec python3 -c "
import sys
from rapids_core.project_registry import main
main()
" "$@"
