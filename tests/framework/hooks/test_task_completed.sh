#!/usr/bin/env bash
# F2 tests for task-completed hook
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/test_helpers.sh"

HOOK_SCRIPT="$SCRIPT_DIR/../../../rapids-core/hooks/scripts/task-completed.sh"

test_logs_to_timeline() {
    cat > "$TEST_DIR/.rapids/rapids.json" << 'EOF'
    {"project":{"id":"test"},"scope":{"tier":3},"current":{"phase":"implement"},"plugins":[]}
EOF
    echo "{\"session_id\":\"test\",\"task_id\":\"task-123\",\"cwd\":\"$TEST_DIR\"}" \
        | bash "$HOOK_SCRIPT" 2>/dev/null

    assert_file_not_empty "$TEST_DIR/.rapids/audit/timeline.jsonl"
    last_line=$(tail -1 "$TEST_DIR/.rapids/audit/timeline.jsonl")
    assert_json_has_field "$last_line" "event"
}

test_skips_non_rapids() {
    rm -rf "$TEST_DIR/.rapids"
    echo "{\"session_id\":\"test\",\"task_id\":\"task-123\",\"cwd\":\"$TEST_DIR\"}" \
        | bash "$HOOK_SCRIPT" 2>/dev/null
    exit_code=$?
    assert_exit_code 0 "$exit_code"
}

echo "=== TaskCompleted Hook Tests ==="
run_test "logs to timeline" test_logs_to_timeline
run_test "skips non-RAPIDS project" test_skips_non_rapids
