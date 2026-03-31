#!/usr/bin/env bash
# CLAUDE.md generator: reads rapids.json + context, writes CLAUDE.md to cwd
set -euo pipefail

CWD="${1:-.}"
RAPIDS_DIR="$CWD/.rapids"

if [ ! -f "$RAPIDS_DIR/rapids.json" ]; then
    echo "Error: $RAPIDS_DIR/rapids.json not found" >&2
    exit 1
fi

python3 -c "
import sys, json
from pathlib import Path
from rapids_core.claude_md_generator import generate_claude_md

cwd = '$CWD'
rapids_dir = Path(cwd) / '.rapids'
rapids_json = json.loads((rapids_dir / 'rapids.json').read_text())

# Build config from rapids.json
config = {
    'phase': rapids_json.get('current', {}).get('phase', 'implement'),
    'tier': rapids_json.get('scope', {}).get('tier', 1),
    'plugins': rapids_json.get('plugins', []),
    'project_id': rapids_json.get('project', {}).get('id', 'unknown'),
}

# Load accumulated context if present
context_path = rapids_dir / 'context' / 'accumulated.json'
if context_path.is_file():
    config['accumulated_context'] = json.loads(context_path.read_text())

result = generate_claude_md(config)
output_path = Path(cwd) / 'CLAUDE.md'
output_path.write_text(result)
print(f'Generated CLAUDE.md ({len(result.splitlines())} lines)')
"
