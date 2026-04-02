#!/usr/bin/env bash
# ASCII banner wrapper: generates RAPIDS ASCII art banners
# Usage: ascii-banner.sh <command>
# Commands: welcome, phase, transition, activity
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

exec python3 -c "
from rapids_core.ascii_art import main
main()
" "$@"
