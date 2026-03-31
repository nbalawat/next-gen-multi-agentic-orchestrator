#!/usr/bin/env bash
# F2 tests for stop-check hook
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/test_helpers.sh"

HOOK_SCRIPT="$SCRIPT_DIR/../../../rapids-core/hooks/scripts/stop-check.sh"

test_blocks_without_artifacts() {
    cat > "$TEST_DIR/.rapids/rapids.json" << 'EOF'
    {"project":{"id":"test"},"scope":{"tier":3},"current":{"phase":"analysis"},"plugins":[]}
EOF
    # Analysis phase requires solution-design.md — don't create it
    set +e
    result=$(echo "{\"session_id\":\"test\",\"stop_hook_active\":false,\"cwd\":\"$TEST_DIR\"}" \
        | bash "$HOOK_SCRIPT" 2>/dev/null)
    exit_code=$?
    set -e

    assert_exit_code 2 "$exit_code" && \
    echo "$result" | grep -q "solution-design.md"
}

test_allows_with_artifacts() {
    cat > "$TEST_DIR/.rapids/rapids.json" << 'EOF'
    {"project":{"id":"test"},"scope":{"tier":3},"current":{"phase":"analysis"},"plugins":[]}
EOF
    echo "# Solution Design" > "$TEST_DIR/.rapids/phases/analysis/solution-design.md"

    echo "{\"session_id\":\"test\",\"stop_hook_active\":false,\"cwd\":\"$TEST_DIR\"}" \
        | bash "$HOOK_SCRIPT" 2>/dev/null
    exit_code=$?
    assert_exit_code 0 "$exit_code"
}

test_allows_implement_phase() {
    cat > "$TEST_DIR/.rapids/rapids.json" << 'EOF'
    {"project":{"id":"test"},"scope":{"tier":2},"current":{"phase":"implement"},"plugins":[]}
EOF

    echo "{\"session_id\":\"test\",\"stop_hook_active\":false,\"cwd\":\"$TEST_DIR\"}" \
        | bash "$HOOK_SCRIPT" 2>/dev/null
    exit_code=$?
    assert_exit_code 0 "$exit_code"
}

test_skips_non_rapids() {
    rm -rf "$TEST_DIR/.rapids"
    echo "{\"session_id\":\"test\",\"stop_hook_active\":false,\"cwd\":\"$TEST_DIR\"}" \
        | bash "$HOOK_SCRIPT" 2>/dev/null
    exit_code=$?
    assert_exit_code 0 "$exit_code"
}

echo "=== Stop Check Hook Tests ==="
run_test "blocks without required artifacts" test_blocks_without_artifacts
run_test "allows with required artifacts" test_allows_with_artifacts
run_test "allows implement phase (no required artifacts)" test_allows_implement_phase
run_test "skips non-RAPIDS project" test_skips_non_rapids
