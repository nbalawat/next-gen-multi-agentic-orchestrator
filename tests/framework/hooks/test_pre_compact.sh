#!/usr/bin/env bash
# F2 tests for pre-compact hook
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/test_helpers.sh"

HOOK_SCRIPT="$SCRIPT_DIR/../../../rapids-core/hooks/scripts/pre-compact.sh"

test_updates_accumulated_context() {
    cat > "$TEST_DIR/.rapids/rapids.json" << 'EOF'
    {"project":{"id":"test"},"scope":{"tier":3},"current":{"phase":"analysis"},"plugins":[]}
EOF
    echo "{\"session_id\":\"test\",\"cwd\":\"$TEST_DIR\"}" \
        | bash "$HOOK_SCRIPT" 2>/dev/null

    assert_file_not_empty "$TEST_DIR/.rapids/context/accumulated.json"
    content=$(cat "$TEST_DIR/.rapids/context/accumulated.json")
    assert_json_has_field "$content" "last_compacted" && \
    assert_json_has_field "$content" "current_phase"
}

test_regenerates_claude_md() {
    cat > "$TEST_DIR/.rapids/rapids.json" << 'EOF'
    {"project":{"id":"test"},"scope":{"tier":3},"current":{"phase":"plan"},"plugins":[]}
EOF
    echo "{\"session_id\":\"test\",\"cwd\":\"$TEST_DIR\"}" \
        | bash "$HOOK_SCRIPT" 2>/dev/null

    assert_file_exists "$TEST_DIR/CLAUDE.md" && \
    assert_contains "$TEST_DIR/CLAUDE.md" "PLAN"
}

test_skips_non_rapids() {
    rm -rf "$TEST_DIR/.rapids"
    echo "{\"session_id\":\"test\",\"cwd\":\"$TEST_DIR\"}" \
        | bash "$HOOK_SCRIPT" 2>/dev/null
    exit_code=$?
    assert_exit_code 0 "$exit_code"
}

echo "=== PreCompact Hook Tests ==="
run_test "updates accumulated context" test_updates_accumulated_context
run_test "regenerates CLAUDE.md" test_regenerates_claude_md
run_test "skips non-RAPIDS project" test_skips_non_rapids
