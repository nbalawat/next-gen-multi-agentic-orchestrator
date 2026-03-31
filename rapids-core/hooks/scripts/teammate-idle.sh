#!/usr/bin/env bash
# TeammateIdle hook: assigns next unblocked task from the dependency graph
# Input (stdin): {"session_id": "...", "teammate_id": "...", "cwd": "..."}
set -euo pipefail

INPUT=$(cat)
CWD=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cwd','.'))")

RAPIDS_DIR="$CWD/.rapids"

if [ ! -d "$RAPIDS_DIR" ]; then
    exit 0
fi

# Find next unblocked feature for the idle teammate
python3 -c "
import json
from pathlib import Path

rapids_dir = Path('$RAPIDS_DIR')
implement_dir = rapids_dir / 'phases' / 'implement'

# Find feature progress files
progress_files = list(implement_dir.glob('feature-progress-*.json')) if implement_dir.is_dir() else []

pending_features = []
for pf in progress_files:
    try:
        progress = json.loads(pf.read_text())
        if progress.get('status') in ('not_started', 'pending'):
            pending_features.append(progress.get('feature_id', pf.stem))
    except (json.JSONDecodeError, KeyError):
        continue

if pending_features:
    # Output the next feature to work on
    print(json.dumps({'next_feature': pending_features[0], 'pending_count': len(pending_features)}))
else:
    print(json.dumps({'next_feature': None, 'pending_count': 0}))
" 2>&1

exit 0
