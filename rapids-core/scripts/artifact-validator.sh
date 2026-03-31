#!/usr/bin/env bash
# Artifact validator: validates a RAPIDS artifact file
# Usage: artifact-validator.sh <path-to-artifact>
set -euo pipefail

ARTIFACT_PATH="${1:-}"

if [ -z "$ARTIFACT_PATH" ]; then
    echo '{"valid": false, "error": "No artifact path provided"}'
    exit 1
fi

if [ ! -f "$ARTIFACT_PATH" ]; then
    echo '{"valid": false, "error": "File not found: '"$ARTIFACT_PATH"'"}'
    exit 1
fi

python3 -c "
import sys, json
from pathlib import Path
from rapids_core.artifact_validator import validate_feature_spec, validate_dependency_graph, validate_journal_entry

path = Path('$ARTIFACT_PATH')
content = path.read_text()

if path.suffix == '.xml':
    result = validate_feature_spec(content)
elif path.name in ('dependency-graph.json', 'dependencies.json'):
    result = validate_dependency_graph(json.loads(content))
elif 'journal' in path.name or 'timeline' in path.name:
    # Validate last line as journal entry
    lines = [l for l in content.strip().splitlines() if l.strip()]
    if lines:
        result = validate_journal_entry(json.loads(lines[-1]))
    else:
        from rapids_core.models import ValidationResult
        result = ValidationResult(valid=True, warnings=['Empty file'])
else:
    from rapids_core.models import ValidationResult
    result = ValidationResult(valid=True, warnings=['Unknown artifact type'])

json.dump({
    'valid': result.valid,
    'error': result.error,
    'warnings': result.warnings,
}, sys.stdout, indent=2)
print()
"
