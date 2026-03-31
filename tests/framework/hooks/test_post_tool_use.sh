#!/usr/bin/env bash
# F2 tests for post-tool-use hook
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/test_helpers.sh"

HOOK_SCRIPT="$SCRIPT_DIR/../../../rapids-core/hooks/scripts/post-tool-use.sh"

test_logs_cost_entry() {
    cat > "$TEST_DIR/.rapids/rapids.json" << 'EOF'
    {"project":{"id":"test"},"scope":{"tier":3},"current":{"phase":"analysis"},"plugins":[]}
EOF
    echo "{\"session_id\":\"test\",\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"echo hello\"},\"cwd\":\"$TEST_DIR\"}" \
        | bash "$HOOK_SCRIPT" 2>/dev/null

    assert_file_not_empty "$TEST_DIR/.rapids/audit/cost.jsonl"
    last_line=$(tail -1 "$TEST_DIR/.rapids/audit/cost.jsonl")
    assert_json_has_field "$last_line" "ts" && \
    assert_json_has_field "$last_line" "phase"
}

test_logs_to_timeline() {
    cat > "$TEST_DIR/.rapids/rapids.json" << 'EOF'
    {"project":{"id":"test"},"scope":{"tier":3},"current":{"phase":"implement"},"plugins":[]}
EOF
    echo "{\"session_id\":\"test\",\"tool_name\":\"Write\",\"tool_input\":{\"path\":\"test.py\"},\"cwd\":\"$TEST_DIR\"}" \
        | bash "$HOOK_SCRIPT" 2>/dev/null

    assert_file_not_empty "$TEST_DIR/.rapids/audit/timeline.jsonl"
}

test_skips_non_rapids_project() {
    rm -rf "$TEST_DIR/.rapids"
    echo "{\"session_id\":\"test\",\"tool_name\":\"Bash\",\"tool_input\":{},\"cwd\":\"$TEST_DIR\"}" \
        | bash "$HOOK_SCRIPT" 2>/dev/null
    exit_code=$?
    assert_exit_code 0 "$exit_code"
}

echo "=== PostToolUse Hook Tests ==="
run_test "logs cost entry" test_logs_cost_entry
run_test "logs to timeline" test_logs_to_timeline
run_test "skips non-RAPIDS project" test_skips_non_rapids_project
