#!/usr/bin/env bash
# F2 tests for session-start hook
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/test_helpers.sh"

HOOK_SCRIPT="$SCRIPT_DIR/../../../rapids-core/hooks/scripts/session-start.sh"

test_generates_claude_md() {
    cat > "$TEST_DIR/.rapids/rapids.json" << 'EOF'
    {"project":{"id":"test"},"scope":{"tier":3,"phases":["analysis","plan","implement"]},"current":{"phase":"analysis"},"plugins":[]}
EOF
    echo "{\"session_id\":\"test\",\"source\":\"startup\",\"cwd\":\"$TEST_DIR\"}" \
        | bash "$HOOK_SCRIPT" 2>/dev/null

    assert_file_exists "$TEST_DIR/CLAUDE.md" && \
    assert_contains "$TEST_DIR/CLAUDE.md" "ANALYSIS" && \
    assert_file_not_empty "$TEST_DIR/CLAUDE.md"
}

test_logs_to_timeline() {
    cat > "$TEST_DIR/.rapids/rapids.json" << 'EOF'
    {"project":{"id":"test"},"scope":{"tier":3,"phases":["analysis"]},"current":{"phase":"analysis"},"plugins":[]}
EOF
    echo "{\"session_id\":\"test\",\"source\":\"startup\",\"cwd\":\"$TEST_DIR\"}" \
        | bash "$HOOK_SCRIPT" 2>/dev/null

    assert_file_not_empty "$TEST_DIR/.rapids/audit/timeline.jsonl"
    last_line=$(tail -1 "$TEST_DIR/.rapids/audit/timeline.jsonl")
    assert_json_has_field "$last_line" "ts" && \
    assert_json_has_field "$last_line" "event"
}

test_resume_includes_welcome_back() {
    cat > "$TEST_DIR/.rapids/rapids.json" << 'EOF'
    {"project":{"id":"test"},"scope":{"tier":3,"phases":["analysis"]},"current":{"phase":"analysis"},"plugins":[]}
EOF
    echo "{\"session_id\":\"test\",\"source\":\"resume\",\"cwd\":\"$TEST_DIR\"}" \
        | bash "$HOOK_SCRIPT" 2>/dev/null

    assert_contains "$TEST_DIR/CLAUDE.md" "Welcome Back"
}

test_skips_non_rapids_project() {
    rm -rf "$TEST_DIR/.rapids"
    result=$(echo "{\"session_id\":\"test\",\"source\":\"startup\",\"cwd\":\"$TEST_DIR\"}" \
        | bash "$HOOK_SCRIPT" 2>/dev/null)
    exit_code=$?
    assert_exit_code 0 "$exit_code"
}

echo "=== SessionStart Hook Tests ==="
run_test "generates CLAUDE.md" test_generates_claude_md
run_test "logs to timeline" test_logs_to_timeline
run_test "resume includes welcome back" test_resume_includes_welcome_back
run_test "skips non-RAPIDS project" test_skips_non_rapids_project
