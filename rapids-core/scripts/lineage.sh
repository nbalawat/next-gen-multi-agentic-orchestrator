#!/usr/bin/env bash
# Deploy Lineage: trace artifacts and requirements through the delivery pipeline
# Usage: lineage.sh <command> [args]
# Commands: build, trace, trace-forward, export, tree
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

COMMAND="${1:-build}"
RAPIDS_DIR="${2:-.rapids}"

python3 -c "
import sys, json
from rapids_core.lineage import (
    build_lineage_graph, trace_artifact, trace_forward,
    format_lineage_tree, export_lineage_json,
)

command = '$COMMAND'
rapids_dir = '$RAPIDS_DIR'

graph = build_lineage_graph(rapids_dir)

if command == 'build':
    exported = export_lineage_json(graph)
    print(json.dumps(exported, indent=2))

elif command == 'trace':
    ref = sys.argv[3] if len(sys.argv) > 3 else ''
    if not ref:
        print('Usage: lineage.sh trace <rapids_dir> <artifact_ref>', file=sys.stderr)
        sys.exit(1)
    chain = trace_artifact(graph, ref)
    print(format_lineage_tree(chain, title=f'Trace: {ref}'))

elif command == 'trace-forward':
    ref = sys.argv[3] if len(sys.argv) > 3 else ''
    if not ref:
        print('Usage: lineage.sh trace-forward <rapids_dir> <node_ref>', file=sys.stderr)
        sys.exit(1)
    chain = trace_forward(graph, ref)
    print(format_lineage_tree(chain, title=f'Forward trace: {ref}'))

elif command == 'export':
    exported = export_lineage_json(graph)
    print(json.dumps(exported, indent=2))

elif command == 'tree':
    ref = sys.argv[3] if len(sys.argv) > 3 else ''
    chain = trace_forward(graph, ref) if ref else list(graph.nodes.values())
    print(format_lineage_tree(chain, title=f'Lineage: {ref or \"full\"}'))

else:
    print(f'Unknown command: {command}', file=sys.stderr)
    print('Commands: build, trace, trace-forward, export, tree', file=sys.stderr)
    sys.exit(1)
" "$@"
