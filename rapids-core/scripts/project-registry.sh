#!/usr/bin/env bash
# Project registry wrapper: manages tracked RAPIDS projects
# Usage: project-registry.sh <command> [args]
# Commands: list, register, update-phase, deactivate, get
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

python3 -c "
import sys
sys.argv = $(python3 -c "import sys,json; print(json.dumps(sys.argv))" "$0" "$@")
from rapids_core.project_registry import main
main()
" "$@"
