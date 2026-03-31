#!/usr/bin/env bash
# Runner for all F2 hook integration tests
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Ensure we're in the project root for Python module resolution
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:${PYTHONPATH:-}"

echo "========================================"
echo "RAPIDS F2 Hook Integration Tests"
echo "========================================"
echo ""

ALL_PASSED=true

for test_file in "$SCRIPT_DIR"/test_*.sh; do
    if [ "$(basename "$test_file")" = "test_helpers.sh" ]; then
        continue
    fi

    echo ""
    if bash "$test_file"; then
        :
    else
        ALL_PASSED=false
    fi
done

echo ""
echo "========================================"

# Source helpers to get report_results
source "$SCRIPT_DIR/test_helpers.sh"

if [ "$ALL_PASSED" = true ]; then
    echo -e "${GREEN}All hook test suites passed${NC}"
    exit 0
else
    echo -e "${RED}Some hook test suites failed${NC}"
    exit 1
fi
