#!/usr/bin/env bash
# Dependency graph generator: reads feature spec XMLs from a directory, outputs dependency-graph.json
# Usage: dependency-graph-generator.sh [plan_dir]
# Default plan_dir: .rapids/phases/plan
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PLAN_DIR="${1:-.rapids/phases/plan}"

python3 -c "
import sys, json
from rapids_core.dependency_graph_generator import generate_dependency_graph_from_directory

graph = generate_dependency_graph_from_directory('$PLAN_DIR')
json.dump(graph, sys.stdout, indent=2)
print()
"
