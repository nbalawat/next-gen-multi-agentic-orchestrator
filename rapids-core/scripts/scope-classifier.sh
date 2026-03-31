#!/usr/bin/env bash
# Scope classifier wrapper: reads JSON signals from stdin, outputs classification JSON
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

python3 -c "
import sys, json
from rapids_core.scope_classifier import classify_scope

signals = json.load(sys.stdin)
result = classify_scope(signals)
json.dump({
    'tier': result.tier,
    'phases': result.phases,
    'reasoning': result.reasoning
}, sys.stdout, indent=2)
print()
"
