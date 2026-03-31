# RAPIDS v2 — Testing Strategy: Framework Testing vs Project Testing

## The Core Problem

There are two fundamentally different things to test, and they've been conflated:

```
Problem 1: Testing RAPIDS itself
  "I changed how the scope classifier works. Did I break phase routing?"
  "I updated the CLAUDE.md generator. Does the new output cause regressions?"
  "I added a new hook. Does it play well with existing hooks?"

Problem 2: Testing projects orchestrated by RAPIDS
  "Does the payment dashboard feature actually work end-to-end?"
  "Did the Generator produce correct Terraform?"
  "Does the Evaluator catch real bugs?"
```

The pain is that both currently require running full RAPIDS cycles with real LLM calls, which is slow and expensive. The solution is to make most testing LLM-free, and make the LLM testing that remains as cheap as possible.

---

## 1. The Testing Separation

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  RAPIDS FRAMEWORK TESTING                                           │
│  "Does the orchestration machinery work correctly?"                 │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Layer F1: Pure Logic (zero LLM, zero cost)                    │  │
│  │   Scope classifier rules                                      │  │
│  │   Phase router (tier → phase list)                            │  │
│  │   Dependency graph → wave computation                         │  │
│  │   Artifact schema validation                                  │  │
│  │   Plugin manifest validation (governance)                     │  │
│  │   CLAUDE.md composition from templates + overlays             │  │
│  │   rapids.json state transitions                               │  │
│  │   Cost log aggregation                                        │  │
│  │   Feature spec XML parsing                                    │  │
│  │   Hook script input/output contracts                          │  │
│  │   Model resolver (tier + phase + capability → model)          │  │
│  │   Export package assembly                                      │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Layer F2: Hook Integration (zero LLM, near-zero cost)         │  │
│  │   SessionStart hook produces correct CLAUDE.md for each state │  │
│  │   PostToolUse hook appends correct JSONL entries              │  │
│  │   Stop hook validates phase completion correctly              │  │
│  │   PreCompact hook archives and regenerates context            │  │
│  │   WorktreeCreate hook sets up environment correctly           │  │
│  │   TaskCompleted hook updates dependency graph correctly       │  │
│  │   Hooks fire in correct order with correct inputs             │  │
│  │   Hooks handle error cases (missing files, bad JSON)          │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Layer F3: Recorded Replay (zero LLM, near-zero cost)          │  │
│  │   Capture real RAPIDS sessions as recordings                  │  │
│  │   Replay recordings against modified framework                │  │
│  │   Assert same artifacts produced, same hooks fired            │  │
│  │   Regression detection without burning tokens                 │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Layer F4: Lightweight LLM Smoke (cheap, Haiku)                │  │
│  │   Scope classification on 10 sample descriptions              │  │
│  │   CLAUDE.md adherence spot-check                              │  │
│  │   Plugin trigger precision evals                              │  │
│  │   One micro toy project through single phase                  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Layer F5: Full Framework E2E (expensive, rare)                │  │
│  │   Complete RAPIDS cycle on reference toy project              │  │
│  │   Docker-isolated, --dangerously-skip-permissions             │  │
│  │   Run before releases only                                    │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  PROJECT TESTING (testing what RAPIDS builds)                       │
│  "Does the application code that agents wrote actually work?"       │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Layer P1: Generator-Written Tests (runs in worktree)          │  │
│  │   Unit tests (pure logic, minimal mocks)                      │  │
│  │   Integration tests (against emulators, no mocks)             │  │
│  │   Runs automatically after each acceptance criterion          │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Layer P2: Evaluator Verification (separate agent)             │  │
│  │   Re-runs Generator's tests independently                    │  │
│  │   Adds its own acceptance criteria tests                      │  │
│  │   Browser automation (Playwright) for UI features             │  │
│  │   Regression suite after wave merge                           │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Layer P3: Cross-Feature Integration (after wave merge)        │  │
│  │   Full test suite on merged main branch                       │  │
│  │   Smoke tests on running application                          │  │
│  │   API contract verification between services                  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Framework Testing: Layer by Layer

### 2.1 Layer F1: Pure Logic Tests (Zero LLM, Zero Cost)

This is the biggest win. Most of the RAPIDS framework is deterministic logic that can be tested with standard unit tests, no LLM needed.

**What to test and how:**

```python
# tests/framework/test_scope_classifier.py

class TestScopeClassifier:
    """Zero LLM calls. Pure function: signals → tier."""

    def test_bug_fix_classifies_tier_1(self):
        signals = {
            "description": "Fix typo in login error message",
            "files_impacted": 1,
            "new_infrastructure": False,
            "integrations": [],
            "domain_complexity": "low"
        }
        result = classify_scope(signals)
        assert result.tier == 1
        assert result.phases == ["implement"]

    def test_two_integrations_classifies_tier_3(self):
        signals = {
            "description": "Build payment dashboard with Bigtable",
            "files_impacted": 15,
            "new_infrastructure": False,
            "integrations": ["bigtable", "react-dashboard"],
            "domain_complexity": "moderate"
        }
        result = classify_scope(signals)
        assert result.tier == 3
        assert result.phases == ["analysis", "plan", "implement", "deploy"]

    def test_greenfield_platform_classifies_tier_5(self):
        signals = {
            "description": "Build new event-driven payments platform",
            "files_impacted": 100,
            "new_infrastructure": True,
            "integrations": ["pubsub", "bigtable", "dataflow", "cloud-run"],
            "domain_complexity": "high"
        }
        result = classify_scope(signals)
        assert result.tier == 5
        assert "research" in result.phases
        assert "sustain" in result.phases
```

```python
# tests/framework/test_wave_computation.py

class TestWaveComputation:
    """Zero LLM calls. Pure function: dependency graph → waves."""

    def test_independent_features_same_wave(self):
        graph = {
            "features": ["F001", "F003"],
            "dependencies": {}
        }
        waves = compute_waves(graph)
        assert len(waves) == 1
        assert set(waves[0]) == {"F001", "F003"}

    def test_dependent_features_sequential_waves(self):
        graph = {
            "features": ["F001", "F002", "F003", "F004", "F005"],
            "dependencies": {
                "F002": ["F001"],
                "F004": ["F003"],
                "F005": ["F002", "F003"]
            }
        }
        waves = compute_waves(graph)
        assert waves[0] == ["F001", "F003"]  # No deps
        assert waves[1] == ["F002", "F004"]  # Deps on wave 0
        assert waves[2] == ["F005"]           # Deps on wave 0 + 1

    def test_circular_dependency_detected(self):
        graph = {
            "features": ["F001", "F002"],
            "dependencies": {"F001": ["F002"], "F002": ["F001"]}
        }
        with pytest.raises(CircularDependencyError):
            compute_waves(graph)
```

```python
# tests/framework/test_model_resolver.py

class TestModelResolver:
    """Zero LLM calls. Pure function: (tier, phase, capability) → model config."""

    def test_tier_1_uses_haiku(self):
        result = resolve_model(tier=1, phase="implement", capability=None)
        assert result.model == "haiku"
        assert result.effort == "low"

    def test_tier_3_analysis_uses_opus(self):
        result = resolve_model(tier=3, phase="analysis", capability="gcp-architecture-design")
        assert result.model == "opus"
        assert result.effort == "high"

    def test_tier_3_implement_uses_sonnet(self):
        result = resolve_model(tier=3, phase="implement", capability="terraform-authoring")
        assert result.model == "sonnet"
        assert result.effort == "medium"

    def test_user_override_takes_precedence(self):
        result = resolve_model(
            tier=3, phase="implement", capability="terraform-authoring",
            user_override={"model": "opus", "effort": "high"}
        )
        assert result.model == "opus"

    def test_plugin_minimum_model_respected(self):
        result = resolve_model(
            tier=2, phase="implement", capability="terraform-authoring",
            plugin_minimum={"model": "sonnet"}
        )
        # Tier 2 default would be haiku, but plugin requires sonnet
        assert result.model == "sonnet"
```

```python
# tests/framework/test_claude_md_generator.py

class TestClaudeMdGenerator:
    """Zero LLM calls. Tests string composition logic."""

    def test_analysis_phase_includes_plugin_overlays(self):
        config = {
            "phase": "analysis",
            "tier": 3,
            "plugins": ["rapids-gcp", "rapids-react"],
            "accumulated_context": {"key_decisions": ["Use Bigtable"]}
        }
        result = generate_claude_md(config, plugin_overlays={
            "rapids-gcp": "Consider GCP services...",
            "rapids-react": "Design component hierarchy..."
        })
        assert "Consider GCP services" in result
        assert "Design component hierarchy" in result
        assert "Use Bigtable" in result
        assert len(result.split("\n")) < 200  # Under 200 lines

    def test_tier_1_generates_minimal_claude_md(self):
        config = {"phase": "implement", "tier": 1, "plugins": []}
        result = generate_claude_md(config, plugin_overlays={})
        assert len(result.split("\n")) < 50  # Very minimal
```

```python
# tests/framework/test_artifact_validation.py

class TestArtifactValidation:
    """Zero LLM calls. Tests schema compliance."""

    def test_valid_feature_spec_passes(self):
        xml = '''<feature id="F001" version="1.0" priority="high" depends_on="" plugin="gcp">
            <n>Bigtable Schema</n>
            <description>Design schema</description>
            <acceptance_criteria>
                <criterion>Supports time-range queries</criterion>
            </acceptance_criteria>
            <estimated_complexity>M</estimated_complexity>
        </feature>'''
        assert validate_feature_spec(xml) == True

    def test_feature_spec_missing_criteria_fails(self):
        xml = '''<feature id="F001" version="1.0" priority="high" depends_on="" plugin="gcp">
            <n>Bigtable Schema</n>
            <description>Design schema</description>
            <estimated_complexity>M</estimated_complexity>
        </feature>'''
        result = validate_feature_spec(xml)
        assert result.valid == False
        assert "acceptance_criteria" in result.error

    def test_dependency_graph_valid_json_schema(self):
        graph = {
            "features": ["F001", "F002"],
            "dependencies": {"F002": ["F001"]},
            "waves": [{"wave": 1, "features": ["F001"]}, {"wave": 2, "features": ["F002"]}]
        }
        assert validate_dependency_graph(graph) == True
```

```python
# tests/framework/test_plugin_governance.py

class TestPluginGovernance:
    """Zero LLM calls. Tests manifest and overlay validation."""

    def test_valid_manifest_passes(self, tmp_path):
        create_minimal_plugin(tmp_path / "rapids-test")
        result = validate_plugin(tmp_path / "rapids-test")
        assert result.valid == True

    def test_duplicate_capability_id_fails(self, tmp_path, existing_plugins):
        # Existing plugin already has "gcp-architecture-design"
        create_plugin_with_capability(tmp_path / "rapids-test", "gcp-architecture-design")
        result = validate_plugin(tmp_path / "rapids-test", existing_plugins)
        assert result.valid == False
        assert "capability ID collision" in result.error

    def test_overlay_with_absolute_directive_warns(self, tmp_path):
        create_plugin_with_overlay(tmp_path / "rapids-test",
            overlay_content="You MUST always use Cloud Functions")
        result = validate_plugin(tmp_path / "rapids-test")
        assert len(result.warnings) > 0
        assert "absolute directive" in result.warnings[0]
```

**How many tests at this layer?** Dozens to hundreds. They run in under 5 seconds. Zero cost. Run on every commit. This is where 80% of your RAPIDS framework confidence comes from.

### 2.2 Layer F2: Hook Integration Tests (Zero LLM, Near-Zero Cost)

Hooks are shell scripts that receive JSON on stdin and produce JSON on stdout. They can be tested by piping mock JSON through them and checking the output, without any LLM involvement.

```bash
# tests/framework/hooks/test_session_start.sh

# Setup: create a minimal .rapids/ directory with known state
setup_test_rapids_dir() {
    mkdir -p "$TEST_DIR/.rapids/phases/analysis"
    cat > "$TEST_DIR/.rapids/rapids.json" << 'EOF'
    {"project":{"id":"test"},"scope":{"tier":3,"phases":["analysis","plan","implement"]},"current":{"phase":"analysis"}}
    EOF
    echo '{"key_decisions":["Use Bigtable"]}' > "$TEST_DIR/.rapids/context/accumulated.json"
}

# Test: SessionStart hook produces valid CLAUDE.md
test_session_start_generates_claude_md() {
    setup_test_rapids_dir
    echo '{"session_id":"test","source":"startup","cwd":"'$TEST_DIR'"}' \
        | bash "$RAPIDS_ROOT/hooks/scripts/session-start.sh"

    # Assert CLAUDE.md was created
    assert_file_exists "$TEST_DIR/CLAUDE.md"

    # Assert it contains phase instructions
    assert_contains "$TEST_DIR/CLAUDE.md" "ANALYSIS"

    # Assert it contains accumulated context
    assert_contains "$TEST_DIR/CLAUDE.md" "Bigtable"

    # Assert it's under 200 lines
    line_count=$(wc -l < "$TEST_DIR/CLAUDE.md")
    assert_less_than "$line_count" 200
}

# Test: SessionStart on resume includes resumption brief
test_session_start_resume_includes_brief() {
    setup_test_rapids_dir
    echo '{"session_id":"test","source":"resume","cwd":"'$TEST_DIR'"}' \
        | bash "$RAPIDS_ROOT/hooks/scripts/session-start.sh"

    assert_contains "$TEST_DIR/CLAUDE.md" "Welcome back"
}
```

```bash
# tests/framework/hooks/test_post_tool_use.sh

# Test: PostToolUse appends cost entry to cost.jsonl
test_post_tool_use_logs_cost() {
    setup_test_rapids_dir
    echo '{"session_id":"test","tool_name":"Bash","tool_input":{"command":"echo hello"},"cwd":"'$TEST_DIR'"}' \
        | bash "$RAPIDS_ROOT/hooks/scripts/post-tool-use.sh"

    # Assert cost.jsonl has a new entry
    assert_file_not_empty "$TEST_DIR/.rapids/audit/cost.jsonl"

    # Assert entry has required fields
    last_line=$(tail -1 "$TEST_DIR/.rapids/audit/cost.jsonl")
    assert_json_has_field "$last_line" "ts"
    assert_json_has_field "$last_line" "phase"
}

# Test: PostToolUse validates artifact if one was created
test_post_tool_use_validates_artifact() {
    setup_test_rapids_dir
    # Simulate a Write tool that created a feature spec
    echo '{"session_id":"test","tool_name":"Write","tool_input":{"path":"'$TEST_DIR'/.rapids/phases/plan/features/F001.xml","content":"<invalid/>"},"cwd":"'$TEST_DIR'"}' \
        | bash "$RAPIDS_ROOT/hooks/scripts/post-tool-use.sh"

    # Assert validation warning was produced
    # (hook output contains feedback about invalid artifact)
}
```

```bash
# tests/framework/hooks/test_stop_check.sh

# Test: Stop hook blocks phase exit when required artifacts missing
test_stop_blocks_without_artifacts() {
    setup_test_rapids_dir
    # Analysis phase requires solution-design.md — don't create it

    result=$(echo '{"session_id":"test","stop_hook_active":false,"cwd":"'$TEST_DIR'"}' \
        | bash "$RAPIDS_ROOT/hooks/scripts/stop-check.sh")

    # Hook should exit with code 2 (block stop, send feedback)
    assert_exit_code 2
    assert_contains "$result" "solution-design.md"
}

# Test: Stop hook allows phase exit when artifacts present
test_stop_allows_with_artifacts() {
    setup_test_rapids_dir
    echo "# Solution Design" > "$TEST_DIR/.rapids/phases/analysis/solution-design.md"

    echo '{"session_id":"test","stop_hook_active":false,"cwd":"'$TEST_DIR'"}' \
        | bash "$RAPIDS_ROOT/hooks/scripts/stop-check.sh"

    assert_exit_code 0
}
```

**These tests run in milliseconds.** They validate that the hook scripts correctly process JSON input, read/write the right files, and produce the right exit codes. No LLM needed because hooks are deterministic shell scripts.

### 2.3 Layer F3: Recorded Replay Tests (Zero LLM, Near-Zero Cost)

This is the key innovation for testing RAPIDS framework changes without burning tokens. The idea: capture a real RAPIDS session as a recording, then replay the framework logic against it.

**How it works:**

```
Step 1: CAPTURE (done once, during a real RAPIDS session)

  Real RAPIDS session running on a toy project:
  ├── Every hook input/output is recorded
  ├── Every artifact created is captured
  ├── Every rapids.json state transition is captured
  ├── Every CLAUDE.md generated is captured
  ├── Every model resolution decision is captured
  └── Saved to: tests/framework/recordings/tier3-payment-dashboard/

Step 2: REPLAY (done on every framework change, zero LLM)

  Modified framework logic replays against the recording:
  ├── Feed recorded hook inputs through updated hook scripts
  ├── Feed recorded signals through updated scope classifier
  ├── Feed recorded artifacts through updated validators
  ├── Feed recorded state through updated CLAUDE.md generator
  └── Compare outputs against recorded baseline

Step 3: DIFF (automated)

  If outputs differ from recording:
  ├── Expected: CLAUDE.md contains "Consider GCP services..."
  ├── Got:      CLAUDE.md contains "Evaluate cloud providers..."
  └── Developer reviews: is this an improvement or a regression?
```

**Recording format:**

```json
// tests/framework/recordings/tier3-payment-dashboard/recording.jsonl
{"step":1,"type":"onboard","input":{"description":"Build payment dashboard","cwd":"/test","has_git":true},"output":{"tier":3,"plugins":["rapids-gcp","rapids-react"]}}
{"step":2,"type":"hook","event":"SessionStart","input":{"source":"startup","cwd":"/test"},"output":{"claude_md_hash":"abc123","claude_md_lines":142}}
{"step":3,"type":"phase_enter","phase":"analysis","rapids_json_after":{"current":{"phase":"analysis"}}}
{"step":4,"type":"artifact_created","path":".rapids/phases/analysis/solution-design.md","content_hash":"def456","validation":"pass"}
{"step":5,"type":"hook","event":"PostToolUse","input":{"tool_name":"Write","tool_input":{"path":".rapids/phases/analysis/solution-design.md"}},"output":{"cost_logged":true,"timeline_logged":true}}
{"step":6,"type":"phase_gate","phase":"analysis","decision":"approved"}
{"step":7,"type":"phase_transition","from":"analysis","to":"plan","rapids_json_after":{"current":{"phase":"plan"}}}
{"step":8,"type":"hook","event":"SessionStart","input":{"source":"startup","cwd":"/test"},"output":{"claude_md_hash":"ghi789","claude_md_lines":128}}
{"step":9,"type":"wave_computation","input":{"features":["F001","F002","F003"],"dependencies":{"F002":["F001"]}},"output":{"waves":[[["F001","F003"],["F002"]]]}}
```

**Replay test:**

```python
# tests/framework/test_replay.py

class TestRecordedReplay:
    """Replay recorded sessions against the current framework.
    Zero LLM calls. Catches regressions in framework logic."""

    @pytest.fixture
    def recording(self):
        return load_recording("tests/framework/recordings/tier3-payment-dashboard/")

    def test_scope_classification_matches(self, recording):
        """The scope classifier produces the same tier for the same input."""
        onboard_step = recording.get_step("onboard")
        result = classify_scope(onboard_step.input)
        assert result.tier == onboard_step.output["tier"]

    def test_claude_md_generation_matches(self, recording):
        """CLAUDE.md generation for each phase produces compatible output."""
        for step in recording.get_steps("hook", event="SessionStart"):
            config = extract_config_from_recording(recording, step)
            result = generate_claude_md(config)
            # Don't require exact match (content evolves), but check structure
            assert abs(len(result.split("\n")) - step.output["claude_md_lines"]) < 20
            assert_contains_phase_instructions(result, config["phase"])

    def test_wave_computation_matches(self, recording):
        """Wave computation produces the same waves for the same dependency graph."""
        wave_step = recording.get_step("wave_computation")
        result = compute_waves(wave_step.input)
        assert result == wave_step.output["waves"]

    def test_all_artifacts_validate(self, recording):
        """All artifacts from the recording still pass validation."""
        for step in recording.get_steps("artifact_created"):
            content = recording.get_artifact_content(step.path)
            result = validate_artifact(step.path, content)
            assert result.valid, f"Artifact {step.path} failed validation: {result.error}"

    def test_hook_outputs_compatible(self, recording):
        """Hook scripts produce compatible outputs for recorded inputs."""
        for step in recording.get_steps("hook"):
            result = run_hook_script(step.event, step.input)
            assert_compatible_output(result, step.output)
```

**Capture script (run once to create a recording):**

```bash
#!/bin/bash
# scripts/capture-recording.sh
# Run this during a real RAPIDS session to create a test recording

RECORDING_DIR="tests/framework/recordings/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RECORDING_DIR/artifacts"

# Wrap each hook script to capture input/output
export RAPIDS_RECORDING_DIR="$RECORDING_DIR"
export RAPIDS_RECORDING_ENABLED=1

# The hooks detect RAPIDS_RECORDING_ENABLED and:
# 1. Save their stdin (JSON input) to $RECORDING_DIR/step-NNN-input.json
# 2. Save their stdout (JSON output) to $RECORDING_DIR/step-NNN-output.json
# 3. Copy any created artifacts to $RECORDING_DIR/artifacts/
# 4. Append a summary line to $RECORDING_DIR/recording.jsonl
```

**When to create new recordings:**
- After a successful E2E test (cheap — you already paid for the LLM calls)
- After a significant feature addition (new phase support, new plugin)
- When a recording becomes stale (framework behavior has intentionally changed)

**Key insight: Recordings are the "golden master" for RAPIDS framework behavior.** They capture what a working system does, so you can detect when a change breaks something — without re-running the LLM. Most framework changes (refactoring hook scripts, optimizing the scope classifier, adjusting CLAUDE.md templates) can be validated entirely through replay tests.

### 2.4 Layer F4: Lightweight LLM Smoke Tests (Cheap, Haiku)

When you need to test that the LLM actually behaves correctly with your framework changes, use the cheapest possible setup:

```yaml
# tests/framework/smoke/scope-classification-llm.yaml
# Uses Haiku at low effort — ~$0.01 per run

test_cases:
  - description: "LLM classifies bug fix correctly"
    prompt: |
      Classify this work request into a scope tier (1-5):
      "Fix the null pointer exception in the login handler"
    model: haiku
    effort: low
    assert:
      - type: contains
        value: "Tier 1"

  - description: "LLM classifies new feature correctly"
    prompt: |
      Classify this work request into a scope tier (1-5):
      "Build a payment reconciliation dashboard that reads from
       Bigtable and displays real-time transaction matching"
    model: haiku
    effort: low
    assert:
      - type: contains
        value: "Tier 3"
```

```yaml
# tests/framework/smoke/plugin-trigger.yaml
# Uses Haiku at low effort — ~$0.02 per run

test_cases:
  - description: "GCP skill triggers for GCP architecture request"
    setup:
      skills_loaded: ["rapids-gcp:gcp-architecture"]
    prompt: "Design the cloud architecture for our transaction system on Google Cloud"
    model: haiku
    effort: low
    assert:
      - type: skill_invoked
        skill: "rapids-gcp:gcp-architecture"

  - description: "GCP skill does NOT trigger for React component request"
    setup:
      skills_loaded: ["rapids-gcp:gcp-architecture", "rapids-react:react-design"]
    prompt: "Create a React component for the transaction list"
    model: haiku
    effort: low
    assert:
      - type: skill_not_invoked
        skill: "rapids-gcp:gcp-architecture"
```

**Cost:** ~$0.05 for a full smoke suite (10-20 test cases on Haiku). Run on every PR that touches LLM-facing code (prompts, skill descriptions, CLAUDE.md templates).

### 2.5 Layer F5: Full Framework E2E (Expensive, Rare)

This is the full RAPIDS cycle on a toy project. Run in Docker, fully autonomous, using `claude -p --dangerously-skip-permissions`.

```yaml
# tests/framework/e2e/tier2-todo-enhancement.yaml
name: "Todo API Enhancement — Tier 2"
description: "Add due_date field to existing Todo API. Validates full RAPIDS cycle."
budget: "$5 max"
model_cap: "sonnet"  # Don't use opus for framework E2E — too expensive

setup:
  codebase: fixtures/todo-api/   # Minimal working Express + PostgreSQL app
  plugins: [rapids-plugin-fullstack]

steps:
  - action: "/rapids-core:start Add a due_date field to todos with validation"
    expect:
      - rapids_json_created: true
      - tier: 2
      - phases: ["plan", "implement"]

  - action: "/rapids-core:go"  # Enter plan phase
    expect:
      - artifacts_created: [".rapids/phases/plan/features/*.xml"]
      - dependency_graph_created: true

  - action: "/rapids-core:go"  # Enter implement phase
    gate_responses: { plan: "approve" }
    expect:
      - worktrees_created: true
      - feature_progress_files_created: true

  - action: "wait_for_completion"
    timeout: 15m
    expect:
      - all_features_complete: true
      - tests_pass: true
      - worktrees_cleaned: true
      - audit_trail_valid: true
      - cost_under: 5.00
```

**Run frequency:** Before releases. After major framework changes. Weekly at most.
**Cost:** $3-10 per run (Tier 2 with Sonnet). $10-30 for a Tier 3 multi-plugin scenario.

---

## 3. What to Test When You Change What

This is the practical guide: "I just changed X in the RAPIDS framework. What tests do I run?"

```
┌─────────────────────────────────────────────────────────────────────┐
│ WHAT YOU CHANGED              │ TESTS TO RUN           │ COST      │
├───────────────────────────────┼────────────────────────┼───────────┤
│ Scope classifier logic        │ F1 (unit) + F3 (replay)│ $0        │
│ Phase routing table           │ F1 (unit) + F3 (replay)│ $0        │
│ Wave computation algorithm    │ F1 (unit) + F3 (replay)│ $0        │
│ Artifact schema/validator     │ F1 (unit) + F3 (replay)│ $0        │
│ Plugin governance rules       │ F1 (unit)              │ $0        │
│ Model resolver logic          │ F1 (unit) + F3 (replay)│ $0        │
│ Cost tracking/aggregation     │ F1 (unit) + F2 (hooks) │ $0        │
│ Export package generation     │ F1 (unit) + F3 (replay)│ $0        │
│ rapids.json schema change     │ F1 (unit) + F3 (replay)│ $0        │
│                               │                        │           │
│ Hook script (any)             │ F2 (hook integration)  │ $0        │
│ SessionStart hook             │ F2 + F3 (replay)       │ $0        │
│ PostToolUse hook              │ F2 + F3 (replay)       │ $0        │
│ Stop hook                     │ F2 + F3 (replay)       │ $0        │
│ WorktreeCreate hook           │ F2 (hook integration)  │ $0        │
│                               │                        │           │
│ CLAUDE.md template/generator  │ F1 + F3 + F4 (smoke)   │ ~$0.05    │
│ Skill description text        │ F4 (trigger smoke)     │ ~$0.02    │
│ Agent prompt/instructions     │ F4 (smoke)             │ ~$0.05    │
│ Phase template content        │ F3 (replay) + F4       │ ~$0.05    │
│ Plugin overlay content        │ F4 (smoke)             │ ~$0.02    │
│                               │                        │           │
│ New plugin added              │ F1 (governance) + F4   │ ~$0.05    │
│ Major architectural change    │ F1 + F2 + F3 + F4 + F5 │ $5-30     │
│ Pre-release validation        │ All layers             │ $5-30     │
└─────────────────────────────────────────────────────────────────────┘
```

**The headline number: 90% of framework changes can be tested for $0.** Only prompt/template/skill description changes need LLM smoke tests (~$0.05). Only major changes or releases need the full E2E ($5-30).

---

## 4. Project Testing: How It Fits

Project testing (testing the code that RAPIDS agents write) is fundamentally different — it always involves running the application code and usually involves LLM calls to write that code. But we can still optimize.

### 4.1 The Cost Breakdown of a Typical RAPIDS Implementation

```
Tier 3 project, 7 features, 4 waves:

Phase                    Tokens        Cost      % of Total
───────────────────────────────────────────────────────────
Analysis (Opus)          ~200K out     ~$15.00   35%
Plan (Sonnet)            ~50K out      ~$0.75    2%
Implement - Generators   ~300K out     ~$4.50    11%
Implement - Evaluators   ~150K out     ~$2.25    5%
Implement - Retries      ~100K out     ~$1.50    4%
Context/overhead         ~800K in      ~$2.40    6%
───────────────────────────────────────────────────────────
                                  ≈ $26.40    (estimate)
```

Analysis is the biggest cost because it runs Opus. Implementation is cheaper per feature but adds up across multiple features.

### 4.2 Optimization Strategies for Project Testing

**Strategy 1: Cache analysis artifacts across similar projects.**
If you've already done analysis for a "React + GCP + Bigtable" project, the architecture patterns are reusable. RAPIDS can offer to start from a template rather than re-deriving everything.

```
/rapids-core:start Build a similar dashboard but for inventory tracking

RAPIDS: "I see you've built a similar project (payment-recon-dashboard)
with the same stack. Would you like to start from its analysis artifacts
as a template, or do fresh analysis?"

User: "Use the template"

RAPIDS: [Copies architecture patterns, adjusts for inventory domain]
        [Saves ~$15 in Analysis phase Opus costs]
```

**Strategy 2: Progressive Evaluator depth.**
Not every feature needs the full 7-step Evaluator verification. Scale the evaluator based on feature complexity:

```yaml
evaluator_depth:
  simple_feature:     # < 3 acceptance criteria, single package
    steps: [static_analysis, unit_tests, acceptance_criteria]
    model: haiku
    # Skips: baseline check, regression, browser verification
    # Cost: ~$0.05

  standard_feature:   # 3-6 acceptance criteria, may cross packages
    steps: [static_analysis, unit_tests, integration_tests, acceptance_criteria]
    model: sonnet
    # Skips: browser verification (no UI)
    # Cost: ~$0.30

  complex_feature:    # UI component, cross-cutting, 6+ criteria
    steps: [all seven steps]
    model: sonnet
    # Full verification including Playwright
    # Cost: ~$0.75
```

**Strategy 3: Run project tests locally without RAPIDS overhead.**
The tests that RAPIDS agents write are just normal test files. You can run them directly without going through the RAPIDS framework:

```bash
# Run all project tests directly (zero RAPIDS overhead)
cd payment-recon-dashboard
npm test                    # Unit tests
npm run test:integration    # Integration tests (needs emulators running)
npx playwright test         # E2E tests

# These are the same tests the Evaluator runs,
# but without the RAPIDS agent orchestration cost
```

**Strategy 4: Incremental evaluation after wave merges.**
Instead of evaluating every feature independently AND running cross-feature tests after merge, run a single combined evaluation after the wave merge:

```
Current (expensive):
  F001 evaluated → $0.30
  F003 evaluated → $0.30
  Wave 1 merge → cross-feature tests → $0.50
  Total: $1.10

Optimized:
  F001 self-tests pass (Generator runs its own tests) → $0 extra
  F003 self-tests pass (Generator runs its own tests) → $0 extra
  Wave 1 merge → Evaluator runs combined suite → $0.50
  Total: $0.50
```

The trade-off: catching bugs earlier (per-feature evaluation) vs catching them at wave merge (combined evaluation). For Tier 2-3, combined evaluation is usually fine. For Tier 4-5 or client environments, per-feature evaluation is safer.

---

## 5. Practical CI/CD Integration

### 5.1 Framework CI (on every PR to rapids-core)

```yaml
# .github/workflows/rapids-framework-ci.yml
name: RAPIDS Framework CI

on: [pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements-test.txt
      - run: pytest tests/framework/test_*.py -v
      # Cost: $0, Time: ~10 seconds

  hook-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: bash tests/framework/hooks/run_all_hook_tests.sh
      # Cost: $0, Time: ~5 seconds

  replay-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pytest tests/framework/test_replay.py -v
      # Cost: $0, Time: ~15 seconds
      # Uses recordings from tests/framework/recordings/

  llm-smoke:
    runs-on: ubuntu-latest
    if: contains(github.event.pull_request.labels.*.name, 'touches-prompts')
    steps:
      - uses: actions/checkout@v4
      - run: pytest tests/framework/smoke/ -v
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      # Cost: ~$0.05, Time: ~30 seconds
      # Only runs if PR is labeled 'touches-prompts'
```

### 5.2 Framework Nightly (full validation)

```yaml
# .github/workflows/rapids-framework-nightly.yml
name: RAPIDS Framework Nightly

on:
  schedule:
    - cron: '0 2 * * *'  # 2 AM daily

jobs:
  full-suite:
    runs-on: ubuntu-latest
    steps:
      - run: pytest tests/framework/ -v         # F1 + F2 + F3
      - run: pytest tests/framework/smoke/ -v   # F4
      # Cost: ~$0.05/night

  e2e-weekly:
    if: github.event.schedule == '0 2 * * 0'  # Sundays only
    runs-on: ubuntu-latest
    container: rapids-test-runner:latest
    steps:
      - run: rapids-test e2e tier2-todo-enhancement
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      # Cost: ~$5, Time: ~15 minutes
      # Only runs weekly
```

---

## 6. Summary: The Testing Cost Model

```
Framework Testing (testing RAPIDS itself):
──────────────────────────────────────────
  F1 Pure Logic:      $0/run      every commit     ~10s
  F2 Hook Integration: $0/run      every commit     ~5s
  F3 Recorded Replay:  $0/run      every commit     ~15s
  F4 LLM Smoke:       ~$0.05/run   prompt changes   ~30s
  F5 Full E2E:        ~$5-30/run   releases         ~15-30min
  ──────────────────────────────────────────
  Typical weekly cost: < $1 (unless releasing)

Project Testing (testing what RAPIDS builds):
──────────────────────────────────────────
  P1 Generator Tests:  included in implementation cost
  P2 Evaluator:        $0.05-0.75/feature (scaled by complexity)
  P3 Cross-Feature:    $0.50/wave
  ──────────────────────────────────────────
  Typical Tier 3 project: $3-8 total for all project testing

Optimizations that save the most:
──────────────────────────────────────────
  1. Recorded replay tests           saves ~$50-100/week
     (catch regressions without LLM)
  2. Haiku for smoke tests           saves ~90% vs Sonnet
  3. Progressive evaluator depth     saves ~50% on project testing
  4. Analysis template reuse         saves ~$15/similar project
  5. Combined wave evaluation        saves ~40% on evaluator costs
```

The recorded replay system is the single biggest efficiency gain. It turns what would be a $5-30 E2E test into a $0 replay test for 90% of framework changes.
