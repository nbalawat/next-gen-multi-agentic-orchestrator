# RAPIDS v2 — Claude Code Feature Coverage Addendum

Eight Claude Code features need to be incorporated into the architecture. This document specifies exactly where each one fits and how it changes the existing design.

---

## 1. /batch — Wave Execution Alternative

**What it is:** Runs the same task across multiple files/directories in parallel, each in its own worktree. Spawns 5-30 independent workers. Automatic PR creation per unit.

**Where it fits in RAPIDS:**

The current architecture uses Agent Teams for wave execution (lead coordinates teammates). `/batch` is a lighter-weight alternative when features in a wave are truly independent — no cross-feature coordination needed, no shared context, no mid-task messaging between workers.

**Decision rule — Agent Teams vs /batch:**

```
Use Agent Teams when:
  - Features in the wave need to coordinate (shared APIs, contracts)
  - The lead needs to monitor and adapt mid-wave
  - Features span multiple plugins (GCP + React in same wave)
  - Tier 4-5 (complex, needs oversight)

Use /batch when:
  - Features in the wave are fully independent
  - Each feature is scoped to a single package/directory
  - No cross-feature contracts to negotiate
  - Tier 2-3 (simpler, well-specified features)
```

**Implementation change:** The wave executor checks the dependency graph. If all features in a wave are independent (no shared reads/writes) and single-plugin, it uses `/batch` instead of Agent Teams. This is faster and cheaper — `/batch` handles worktree isolation, parallel execution, and PR creation natively.

**Updated pipeline:**
```
Wave N starts
├── Check features: independent? single-plugin? 
│   ├── YES → /batch "implement feature per spec" across feature directories
│   └── NO  → Agent Teams with lead + per-feature teammates
├── /simplify runs on each completed unit (see below)
├── Evaluator verifies
└── Merge
```

---

## 2. /simplify — Pre-Evaluator Code Review

**What it is:** 3-agent parallel code review (code reuse, code quality, efficiency). Runs automatically, applies fixes, discards false positives.

**Where it fits in RAPIDS:**

Currently the pipeline is Generator → Evaluator. Adding `/simplify` creates: Generator → Simplify → Evaluate. The Generator writes code, `/simplify` polishes it, then the Evaluator verifies the polished result.

**Updated implementation pipeline per feature:**
```
Generator implements feature (in worktree)
    │
    ▼
/simplify runs on changed files
    │ 3 parallel review agents:
    │ - Code reuse agent (dedup, abstractions)
    │ - Code quality agent (readability, structure)  
    │ - Efficiency agent (performance, resources)
    │ Fixes applied automatically. False positives skipped.
    │
    ▼
Evaluator verifies (acceptance criteria, tests, browser)
```

**Why this matters:** The Evaluator's job gets easier because `/simplify` catches the low-hanging issues first. The Evaluator can focus on functional correctness rather than code style, which reduces evaluator iteration count and saves tokens.

**Cost impact:** `/simplify` costs ~$0.10-0.30 per feature (3 Sonnet agents). But it reduces Evaluator retries by catching issues early, often saving more than it costs.

---

## 3. /loop — Progress Polling During Autonomous Mode

**What it is:** Repeats a prompt at a specified interval within a session. Session-scoped (dies when you exit). Cron-based, up to 50 concurrent tasks.

**Where it fits in RAPIDS:**

During autonomous implementation, the user kicks off a wave and steps away. `/loop` provides lightweight monitoring without requiring the user to manually check status.

**RAPIDS usage patterns:**

```bash
# Monitor implementation progress every 5 minutes
/loop 5m "check .rapids/phases/implement/feature-progress/ and tell me how many features are complete vs in-progress vs blocked"

# Monitor build health during Deploy phase  
/loop 3m "run the smoke test suite and alert me if anything fails"

# Watch for evaluator failures during autonomous mode
/loop 2m "check if any evaluator verdicts in the last 2 minutes show 'fail' and summarize the feedback"
```

**Implementation change:** The `/rapids-core:go` skill, when entering Implementation in autonomous mode, automatically sets up a `/loop` that polls feature-progress.json every 5 minutes and surfaces a brief status update. This loop auto-cancels when all features in the current wave complete.

---

## 4. /btw — Side Questions Without Context Disruption

**What it is:** Ask a side question while Claude is mid-response. Uses prompt cache, no tool access, doesn't pollute the main task's context. Single response only.

**Where it fits in RAPIDS:**

During any long-running RAPIDS phase (especially Implementation), the user can ask side questions without derailing the active work:

```
[Generator is mid-implementation of F003...]

User: /btw what's the cost so far for this work item?
Claude: Cost for WI-003: $4.23 (Analysis: $1.85, Plan: $0.42, Implement: $1.96)

[Generator continues undisturbed]
```

```
[Analysis phase is running...]

User: /btw which plugins are active?
Claude: rapids-gcp and rapids-react are active for this project.

[Analysis continues]
```

**Implementation change:** No architectural change needed. This is a Claude Code native feature that works automatically. The `/rapids-core:status` skill content should reference `/btw` as the preferred way to check status mid-task: "Use /btw to ask quick status questions without interrupting the current task."

---

## 5. Auto Mode — Safer Autonomous Execution

**What it is:** AI-powered permission classifier replaces manual approve/reject. A background model evaluates each tool call, blocking dangerous operations and allowing safe ones. Not perfect (17% false-negative on overeager actions) but massively better than `--dangerously-skip-permissions`.

**Where it fits in RAPIDS:**

Auto mode is the **default permission model for RAPIDS autonomous implementation.** Previously the architecture assumed either manual approval (slow) or `--dangerously-skip-permissions` (dangerous). Auto mode is the middle ground.

**Updated permission model by implementation mode:**

```
Autonomous mode:
  → Auto mode enabled (--enable-auto-mode)
  → Background classifier handles permissions
  → Dangerous ops blocked automatically
  → User sees post-hoc summary, not per-action approval

Human-in-the-loop mode:
  → Standard approval mode (default Claude Code behavior)
  → User approves each action
  → Recommended for Tier 4-5, client environments

Hybrid mode:
  → Auto mode within each wave (features run autonomously)
  → Manual approval at wave boundaries (human gate)
  → Default recommendation for most projects
```

**For E2E tests:** Continue using `--dangerously-skip-permissions` inside Docker containers. Auto mode requires the background classifier, which adds latency that's undesirable in test environments.

---

## 6. LSP Servers — Real-Time Diagnostics During Implementation

**What it is:** Plugins can declare Language Server Protocol configurations. Gives Claude instant diagnostics (type errors, missing imports), go-to-definition, and hover info after every edit. The same technology that powers VS Code's intelligence.

**Where it fits in RAPIDS:**

Domain plugins should ship LSP configurations for their language stack. This means the Generator catches type errors immediately after writing code — before tests even run.

**Plugin LSP declarations:**

```json
// rapids-typescript/.lsp.json
{
  "typescript": {
    "command": "typescript-language-server",
    "args": ["--stdio"],
    "extensionToLanguage": {
      ".ts": "typescript",
      ".tsx": "typescriptreact"
    }
  }
}
```

```json
// rapids-python/.lsp.json  
{
  "python": {
    "command": "pylsp",
    "args": [],
    "extensionToLanguage": {
      ".py": "python"
    }
  }
}
```

```json
// rapids-gcp/.lsp.json (for Terraform)
{
  "terraform": {
    "command": "terraform-ls",
    "args": ["serve"],
    "extensionToLanguage": {
      ".tf": "terraform"
    }
  }
}
```

**Updated implementation pipeline:**
```
Generator writes code
    │
    ├── LSP immediately reports errors (type mismatches, missing imports)
    ├── Generator auto-fixes before committing
    │
    ▼
/simplify reviews
    ▼
Evaluator verifies
```

**Impact:** Reduces Evaluator iteration count significantly. Static analysis failures get caught at the Generator stage, not the Evaluator stage. Each avoided Evaluator round-trip saves ~$0.20-0.50 in tokens.

---

## 7. Channels — Event Push from External Systems

**What it is:** MCP servers that push events into a running Claude Code session. Two-way — Claude reads the event and can reply through the same channel. Currently supports Telegram and Discord, with custom channel support.

**Where it fits in RAPIDS:**

For the Deploy and Sustain phases, channels replace polling with event-driven reactions:

```
Deploy phase:
  CI/CD pipeline pushes "build complete" → RAPIDS session reacts
  Cloud deployment pushes "deploy succeeded" → RAPIDS runs smoke tests
  Instead of: /loop 3m "check if the build finished"

Sustain phase:  
  Monitoring alert pushes "error rate spike" → RAPIDS investigates
  PR review pushes "changes requested" → RAPIDS addresses feedback
  Instead of: periodic polling of alerting systems
```

**Implementation change:** The rapids-core plugin can declare a channel MCP server that accepts webhook events from CI/CD systems. The Deploy phase skill registers for deploy-related events. The Sustain phase skill registers for monitoring events.

**For teams using Slack/Discord:** The official channel plugins allow RAPIDS to receive instructions from team chat. A message like "@claude investigate the error spike on the payment service" in Slack dispatches to the active RAPIDS session.

---

## 8. Remote Control — Mobile Monitoring of Autonomous Sessions

**What it is:** Bridge a local Claude Code terminal session to claude.ai/code or the Claude iOS/Android app. The session keeps running on your machine. The web/mobile interface is just a window into the local session.

**Where it fits in RAPIDS:**

For autonomous implementation, Remote Control is the monitoring layer. The user kicks off a wave at their desk, walks away, and monitors from their phone.

**RAPIDS workflow with Remote Control:**

```
At desk:
  /rapids-core:go  (enters autonomous implement mode)
  claude remote-control  (enables mobile access)

On phone (claude.ai/code or iOS app):
  See: "Wave 2 in progress. F002: 3/5 criteria done. F004: complete."
  See: "Gate review needed — Wave 2 complete. 2 features ready for merge."
  Type: "approved, proceed to wave 3"

Back at desk:
  /teleport  (pull session back to terminal for debugging)
```

**Implementation change:** The `/rapids-core:go` skill, when entering autonomous mode, should suggest enabling Remote Control. The status output should be formatted to be readable on a mobile screen (short, structured, not long prose).

---

## 9. Updated Implementation Pipeline (All Features Integrated)

The full pipeline for a feature during the Implement phase now looks like this:

```
Feature F001 starts (in worktree)
│
├── LSP server starts (real-time diagnostics)
│
├── Generator implements incrementally:
│   ├── Pick one acceptance criterion
│   ├── Write code → LSP catches immediate errors → fix
│   ├── Write tests (real, no mocks)
│   ├── Run tests locally
│   ├── Commit with descriptive message
│   ├── Update feature-progress.json
│   └── Repeat for next criterion
│   
│   Permission model: Auto mode (background classifier)
│   User monitoring: Remote Control (phone) + /btw (side questions)
│   Progress polling: /loop 5m (automated status checks)
│
├── /simplify runs on all changed files:
│   ├── Code reuse agent → dedup, extract abstractions
│   ├── Code quality agent → readability, structure
│   ├── Efficiency agent → performance
│   └── Fixes applied automatically
│
├── Evaluator verifies:
│   ├── Static analysis (compiler + LSP diagnostics)
│   ├── Generator's tests (re-run independently)
│   ├── Own acceptance criteria tests
│   ├── Regression check
│   └── Browser verification (Playwright MCP, if UI)
│
├── If pass → merge worktree → update dependency graph
├── If fail → feedback to Generator → retry (max 3)
└── If fail after max → escalate model or flag for human

Wave execution method:
├── Independent features → /batch (lighter, cheaper)
└── Coordinated features → Agent Teams (lead + teammates)

Event-driven (via Channels):
├── CI pushes "tests pass" → advance to next wave
├── Deploy pushes "deploy complete" → run smoke tests
└── Monitor pushes "alert" → investigate in Sustain phase
```

---

## 10. Updated Feature Count in Architecture

```
PREVIOUSLY ACCOUNTED FOR (13):
  Agent Teams, Git Worktrees, Hooks (21 events),
  Skills (2.0 with evals), CLAUDE.md (hierarchical),
  AskUserQuestion, Subagents, Plugin system,
  Marketplace, Headless mode (claude -p),
  Adaptive effort, opusplan, /compact

NOW ADDED (8):
  /batch, /simplify, /loop, /btw, Auto mode,
  LSP servers, Channels, Remote Control

NOTED BUT NOT ARCHITECTURALLY RELEVANT (5):
  /voice, /branch, /teleport, --resume,
  1M context (plan-level feature, not architectural)

ALSO NOTED FOR COMPLETENESS (3):
  OpenTelemetry (enterprise observability),
  --add-dir (polyrepo support),
  Dispatch (external trigger for RAPIDS phases)

TOTAL CLAUDE CODE FEATURES SURVEYED: 29
TOTAL INCORPORATED INTO RAPIDS: 24
```

---

## 11. Sections of Consolidated Document to Update

| Section | What Changes |
|---------|-------------|
| Part 6.3 (Generator-Evaluator) | Pipeline becomes Generator → /simplify → Evaluator |
| Part 6.4 (Wave execution) | Add /batch as alternative to Agent Teams for independent features |
| Part 6.5 (Implementation detail) | Add LSP, auto mode, /loop, Remote Control to the execution flow |
| Part 4.3 (Plugin structure) | Add .lsp.json to plugin directory convention |
| Part 9 (Integration points) | Add /batch, /simplify, /loop, /btw, auto mode, channels, Remote Control, LSP |
| Part 7 (Model right-sizing) | Note that auto mode replaces --dangerously-skip-permissions for autonomous execution |
| Part 8 (Audit trail) | OpenTelemetry as optional enterprise-grade supplement to JSONL logging |
| Part 2 (Phase definitions) | Channels for Deploy/Sustain event-driven reactions. Scheduled tasks for Sustain monitoring loops. |
