#!/usr/bin/env bash
# ASCII banner wrapper: generates RAPIDS ASCII art banners
# Usage: ascii-banner.sh <command>
# Commands: welcome, phase, transition, activity
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

python3 -c "
import sys
sys.argv = $(python3 -c "import sys,json; print(json.dumps(sys.argv))" "$0" "$@")
from rapids_core.ascii_art import main
main()
" "$@"
