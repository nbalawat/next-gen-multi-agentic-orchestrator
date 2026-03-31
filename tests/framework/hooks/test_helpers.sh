#!/usr/bin/env bash
# Test helper functions for F2 hook integration tests

TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0
FAILURES=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

assert_file_exists() {
    if [ -f "$1" ]; then
        return 0
    else
        echo "  ASSERT FAILED: File does not exist: $1"
        return 1
    fi
}

assert_dir_exists() {
    if [ -d "$1" ]; then
        return 0
    else
        echo "  ASSERT FAILED: Directory does not exist: $1"
        return 1
    fi
}

assert_file_not_empty() {
    if [ -s "$1" ]; then
        return 0
    else
        echo "  ASSERT FAILED: File is empty: $1"
        return 1
    fi
}

assert_contains() {
    local file="$1"
    local expected="$2"
    if grep -q "$expected" "$file" 2>/dev/null; then
        return 0
    else
        echo "  ASSERT FAILED: '$file' does not contain '$expected'"
        return 1
    fi
}

assert_not_contains() {
    local file="$1"
    local unexpected="$2"
    if ! grep -q "$unexpected" "$file" 2>/dev/null; then
        return 0
    else
        echo "  ASSERT FAILED: '$file' contains '$unexpected'"
        return 1
    fi
}

assert_exit_code() {
    local expected="$1"
    local actual="$2"
    if [ "$actual" -eq "$expected" ]; then
        return 0
    else
        echo "  ASSERT FAILED: Expected exit code $expected, got $actual"
        return 1
    fi
}

assert_less_than() {
    local actual="$1"
    local limit="$2"
    if [ "$actual" -lt "$limit" ]; then
        return 0
    else
        echo "  ASSERT FAILED: $actual is not less than $limit"
        return 1
    fi
}

assert_json_has_field() {
    local json_str="$1"
    local field="$2"
    if echo "$json_str" | python3 -c "import sys,json; d=json.load(sys.stdin); assert '$field' in d" 2>/dev/null; then
        return 0
    else
        echo "  ASSERT FAILED: JSON does not have field '$field'"
        return 1
    fi
}

# Setup a minimal .rapids/ test directory
setup_test_rapids_dir() {
    TEST_DIR=$(mktemp -d)
    mkdir -p "$TEST_DIR/.rapids/phases/analysis"
    mkdir -p "$TEST_DIR/.rapids/phases/plan"
    mkdir -p "$TEST_DIR/.rapids/phases/implement"
    mkdir -p "$TEST_DIR/.rapids/context"
    mkdir -p "$TEST_DIR/.rapids/audit"
    touch "$TEST_DIR/.rapids/audit/cost.jsonl"
    touch "$TEST_DIR/.rapids/audit/timeline.jsonl"
    echo '{}' > "$TEST_DIR/.rapids/context/accumulated.json"
}

teardown_test_dir() {
    if [ -n "${TEST_DIR:-}" ] && [ -d "$TEST_DIR" ]; then
        rm -rf "$TEST_DIR"
    fi
}

# Run a test function and track results
run_test() {
    local test_name="$1"
    local test_func="$2"
    TESTS_RUN=$((TESTS_RUN + 1))

    # Setup
    setup_test_rapids_dir

    # Run
    if $test_func; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        echo -e "  ${GREEN}PASS${NC}: $test_name"
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        FAILURES="$FAILURES\n  FAIL: $test_name"
        echo -e "  ${RED}FAIL${NC}: $test_name"
    fi

    # Teardown
    teardown_test_dir
}

report_results() {
    echo ""
    echo "========================================"
    echo "F2 Hook Tests: $TESTS_PASSED/$TESTS_RUN passed"
    if [ $TESTS_FAILED -gt 0 ]; then
        echo -e "${RED}Failures:${NC}$FAILURES"
        return 1
    else
        echo -e "${GREEN}All tests passed${NC}"
        return 0
    fi
}
