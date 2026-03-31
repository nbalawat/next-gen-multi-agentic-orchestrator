#!/usr/bin/env bash
# Wave computer: reads dependency graph JSON from stdin, outputs wave plan
set -euo pipefail

python3 -c "
import sys, json
from rapids_core.wave_computer import compute_waves

graph = json.load(sys.stdin)
waves = compute_waves(graph)
output = {
    'waves': [
        {'wave': i + 1, 'features': features}
        for i, features in enumerate(waves)
    ],
    'total_waves': len(waves)
}
json.dump(output, sys.stdout, indent=2)
print()
"
