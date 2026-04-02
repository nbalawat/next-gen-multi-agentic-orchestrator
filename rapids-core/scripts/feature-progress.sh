#!/usr/bin/env bash
# Feature progress: manages per-feature progress tracking files
# Usage: feature-progress.sh <command> [args]
# Commands: init, read, update, aggregate, is-complete
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

exec python3 -c "
from rapids_core.feature_progress import main
main()
" "$@"
