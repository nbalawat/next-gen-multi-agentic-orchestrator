# RAPIDS v2 — AI-Assisted Software Delivery Framework

RAPIDS (Research, Analysis, Plan, Implement, Deploy, Sustain) is an orchestration framework built as a [Claude Code](https://claude.ai/code) plugin system. It structures AI-assisted software delivery through six phases, using scope-based routing, wave execution, and a Generator-Evaluator pattern.

## How It Works

RAPIDS classifies every project into a **scope tier** (1-5) and routes it through the appropriate phases:

```
Tier 1 (bug fix)       → Implement
Tier 2 (enhancement)   → Plan → Implement
Tier 3 (feature)       → Analysis → Plan → Implement → Deploy
Tier 4 (system)        → Research → Analysis → Plan → Implement → Deploy
Tier 5 (platform)      → Research → Analysis → Plan → Implement → Deploy → Sustain
```

During the **Implement** phase, features are organized into dependency-aware **waves** and executed in parallel using either `/batch` (independent features) or **Agent Teams** (coordinated features).

Each feature follows the **Generator-Evaluator** pattern:

```
Generator (writes code, one acceptance criterion at a time)
    → /simplify (3 parallel code review agents)
    → Evaluator (independently verifies correctness)
    → If pass → merge; if fail → retry (max 3)
```

## Project Structure

```
rapids-core/                    # Core orchestration plugin
├── .claude-plugin/plugin.json  # Claude Code plugin manifest
├── skills/                     # 5 user-facing skills
│   ├── start/SKILL.md          #   /rapids-core:start — onboard + classify
│   ├── add/SKILL.md            #   /rapids-core:add — add bug/enhancement/feature
│   ├── status/SKILL.md         #   /rapids-core:status — progress + cost
│   ├── go/SKILL.md             #   /rapids-core:go — advance phases
│   └── export/SKILL.md         #   /rapids-core:export — client deliverables
├── agents/rapids-lead.md       # Lead orchestrator agent
├── hooks/                      # 7 lifecycle hooks
│   ├── hooks.json              #   Event registrations
│   └── scripts/                #   SessionStart, PostToolUse, Stop, etc.
├── scripts/                    # Shell wrappers for Python modules
├── schemas/                    # XML/JSON schemas for artifacts
└── templates/                  # Per-phase artifact templates

rapids-gcp/                     # Reference domain plugin (GCP/Terraform)
├── skills/                     # 5 phase-aware skills
├── agents/                     # gcp-architect, terraform-engineer
├── hooks/                      # GCP-specific worktree setup
└── evals/                      # Trigger precision + quality evals

src/rapids_core/                # Python framework logic
├── scope_classifier.py         # Signals → tier (1-5)
├── phase_router.py             # Tier → phase list
├── wave_computer.py            # Dependency graph → execution waves
├── wave_executor.py            # Batch vs Agent Teams decision
├── model_resolver.py           # (tier, phase) → model config
├── claude_md_generator.py      # Dynamic CLAUDE.md composition
├── artifact_validator.py       # Feature spec + dependency graph validation
├── plugin_governance.py        # Plugin structure + capability collision checks
├── cost_tracker.py             # JSONL cost aggregation
├── plugin_scaffold.py          # Domain plugin generator
├── recording.py                # Session capture/replay for testing
├── project_registry.py         # Central project tracking (~/.rapids/projects.json)
├── ascii_art.py                # Phase banners, activity displays, welcome screen
├── onboarding.py               # AskUserQuestion payloads for /start flow
├── phase_questions.py           # AskUserQuestion payloads for /go flow
├── dependency_graph_generator.py # Feature spec XMLs → dependency-graph.json
├── batch_dispatcher.py          # Dispatch plans for /batch parallel execution
├── agent_team_orchestrator.py   # Multi-agent team plans for Tier 4-5 waves
├── worktree_manager.py          # Git worktree lifecycle (create, merge, cleanup)
├── feature_progress.py          # Per-feature progress tracking across worktrees
└── work_item_manager.py         # Concurrent work items (bugs, features, enhancements)

tests/                          # Multi-layer test suite
├── framework/test_*.py         # F1: 437 unit tests (zero LLM, $0)
├── framework/hooks/            # F2: 16 hook integration tests ($0)
├── framework/recordings/       # F3: Recorded replay tests ($0)
├── framework/smoke/            # F4: LLM smoke tests (~$0.05)
└── framework/e2e/              # F5: Full E2E in Docker ($5-30)
```

## Quick Start

### Prerequisites

- Python 3.11+
- [Claude Code](https://claude.ai/code) CLI

### Install

```bash
git clone https://github.com/nbalawat/next-gen-multi-agentic-orchestrator.git
cd next-gen-multi-agentic-orchestrator
pip install -e ".[dev]"
```

### Run Tests

```bash
make test          # F1: 437 unit tests (~0.3s, $0)
make test-hooks    # F2: 16 hook integration tests ($0)
make test-replay   # F3: Recorded replay tests ($0)
make test-all      # All free tests

# Requires ANTHROPIC_API_KEY
make test-smoke    # F4: LLM smoke tests (~$0.05)
```

### Use as a Claude Code Plugin

```bash
# Start Claude Code with the RAPIDS plugin
claude --plugin-dir ./rapids-core

# In the Claude Code session:
/rapids-core:start
```

On start, RAPIDS displays a welcome banner with all managed projects and asks for:
1. The **working directory** for your project
2. A **description** of what you want to build

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ██████╗   █████╗  ██████╗  ██╗ ██████╗  ███████╗                          ║
║   ██╔══██╗ ██╔══██╗ ██╔══██╗ ██║ ██╔══██╗ ██╔════╝                          ║
║   ██████╔╝ ███████║ ██████╔╝ ██║ ██║  ██║ ███████╗                          ║
║   ██╔══██╗ ██╔══██║ ██╔═══╝  ██║ ██║  ██║ ╚════██║                          ║
║   ██║  ██║ ██║  ██║ ██║      ██║ ██████╔╝ ███████║                          ║
║   ╚═╝  ╚═╝ ╚═╝  ╚═╝ ╚═╝      ╚═╝ ╚═════╝  ╚══════╝                          ║
║                                                                              ║
║   MANAGED PROJECTS                                                           ║
║   ────────────────                                                           ║
║   #    PROJECT              TIER     PHASE          STATUS     DIRECTORY      ║
║   1    payment-dashboard    T3       implement      ● active   /home/dev/pay  ║
║   2    auth-service         T4       analysis       ● active   /home/dev/auth ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

Then use the other skills to drive the project:

```bash
/rapids-core:go         # advance to next phase (shows phase transition banner)
/rapids-core:status     # check progress with visual phase display
/rapids-core:export     # generate client deliverables
```

### Try the Shell Scripts Directly

```bash
# Classify a project's scope
echo '{"description":"Build a dashboard","files_impacted":15,
  "new_infrastructure":false,"integrations":["bigtable","react"],
  "domain_complexity":"moderate"}' | rapids-core/scripts/scope-classifier.sh

# Compute implementation waves
echo '{"features":["F001","F002","F003"],
  "dependencies":{"F002":["F001"]}}' | rapids-core/scripts/wave-computer.sh

# Aggregate costs
rapids-core/scripts/cost-tracker.sh .rapids/audit/cost.jsonl
```

## Domain Plugins

RAPIDS is extensible through domain plugins. Each plugin adds phase-specific skills, agents, and hooks for a technology domain.

### Included: rapids-gcp

GCP architecture, Terraform authoring, Cloud Run deployment, and Cloud Monitoring.

### Create Your Own

Generate a plugin scaffold:

```python
from rapids_core.plugin_scaffold import generate_plugin_scaffold

generate_plugin_scaffold(
    output_dir="./plugins",
    name="rapids-python",
    description="Python/FastAPI backend plugin",
    capabilities={
        "implement": [{"id": "fastapi-impl", "description": "FastAPI implementation"}]
    },
)
```

Or start from the template in `templates/rapids-plugin-template/`.

A minimum viable plugin is 3 files:

```
rapids-my-domain/
├── .claude-plugin/plugin.json    # {"name": "rapids-my-domain"}
├── rapids.plugin.json            # Capabilities and config
└── skills/my-skill/SKILL.md      # Implementation guidance
```

## Architecture

### Phase Artifacts

Each phase produces artifacts stored in `.rapids/phases/`:

| Phase | Key Artifacts |
|-------|--------------|
| Research | Problem statement, domain findings |
| Analysis | Solution design, Architecture Decision Records |
| Plan | Feature specs (XML), dependency graph, wave plan |
| Implement | Code, tests, feature progress, evaluator verdicts |
| Deploy | Deployment config, smoke test results |
| Sustain | Monitoring config, alerting rules, runbooks |

### Project Registry

RAPIDS maintains a **central project registry** at `~/.rapids/projects.json` that tracks all projects under management. This persists across sessions and working directories.

```bash
# Shell scripts for registry management
rapids-core/scripts/project-registry.sh list              # Show all active projects
rapids-core/scripts/project-registry.sh get /path/to/proj  # Look up a specific project
```

Each registered project tracks: name, path, tier, current phase, plugins, status (active/inactive), and timestamps.

### Phase Visualization (ASCII Art)

Every RAPIDS operation displays a clear visual banner showing:
- **Which phase** you're currently in (highlighted in the phase pipeline)
- **What activity** is about to happen
- **Completed phases** (checkmarked) vs **upcoming phases** (circles)

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                  R A P I D S  —  IMPLEMENTATION PHASE                        ║
║                                                                              ║
╟──────────────────────────────────────────────────────────────────────────────╢
║                                                                              ║
║   ✓R✓ ──  ✓A✓ ──  ✓P✓ ── ▐█I█▌ ──  ○D○ ──  ·S·                             ║
║                                                                              ║
║   ✓ [R] RESEARCH         (completed)                                         ║
║   ✓ [A] ARCHITECTURE     (completed)                                         ║
║   ✓ [P] PLANNING         (completed)                                         ║
║   ▶ [I] IMPLEMENTATION   Code, test, commit — one criterion at a time        ║
║   ○ [D] DEPLOYMENT       (upcoming)                                          ║
║   · [S] STABILIZATION    (not in scope)                                      ║
║                                                                              ║
║   ┌────────────────────────────────────────────────────────────┐              ║
║   │  CURRENT ACTIVITY:                                        │              ║
║   │  Wave 2 — Feature F003: Payment Processing                │              ║
║   └────────────────────────────────────────────────────────────┘              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

Phase transitions also get their own banner:

```
╔══════════════════════════════════════════════════════════════════════════════╗
║   ╔══════════════════════════════════════════════════════════════════╗       ║
║   ║   PHASE TRANSITION                                               ║       ║
║   ║        PLANNING  ━━━━▶  IMPLEMENTATION                          ║       ║
║   ╚══════════════════════════════════════════════════════════════════╝       ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### Template-Based Artifact Scaffolding

When a project starts or transitions to a new phase, RAPIDS copies **artifact templates** into the phase directory so you always have a structured starting point:

| Phase | Templates Scaffolded |
|-------|---------------------|
| Research | `problem-statement.md` |
| Analysis | `solution-design.md`, `adr-template.md` |
| Plan | `feature-spec-template.xml` |
| Implement | `evaluator-prompt.md`, `feature-progress-template.json` |

Templates are never overwritten — if you've already started working on an artifact, it's preserved.

### Hooks

RAPIDS uses 7 Claude Code lifecycle hooks:

| Hook | Purpose |
|------|---------|
| SessionStart | Load state, display phase banner, generate CLAUDE.md, handle resume |
| PostToolUse | Cost tracking, audit logging, artifact validation |
| Stop | Phase gate — block exit if required artifacts are missing |
| PreCompact | Archive context before conversation compaction |
| TaskCompleted | Update feature progress and dependency graph |
| TeammateIdle | Assign next unblocked feature |
| WorktreeCreate | Set up plugin-specific environment in worktrees |

### Model Right-Sizing

The model resolver automatically selects the appropriate model based on tier and phase:

| | Analysis | Plan | Implement |
|---|---------|------|-----------|
| Tier 1 | — | — | Haiku |
| Tier 2 | — | Sonnet | Sonnet |
| Tier 3 | Opus | Sonnet | Sonnet |
| Tier 4-5 | Opus | Opus/Sonnet | Sonnet |

### Claude Code Feature Integration

RAPIDS leverages these Claude Code capabilities:

- **/batch** — parallel wave execution for independent features
- **/simplify** — automated 3-agent code review between Generator and Evaluator
- **/loop** — progress polling during autonomous implementation
- **Auto mode** — AI-powered permission classifier for autonomous execution
- **LSP servers** — real-time diagnostics during code generation
- **Channels** — event-driven Deploy/Sustain via CI/CD webhooks
- **Remote Control** — mobile monitoring of autonomous sessions
- **/btw** — side questions without disrupting active work

## Testing Strategy

90% of framework changes are testable for $0:

| Layer | What | Cost | When |
|-------|------|------|------|
| F1 | 140 pytest unit tests on pure logic | $0 | Every commit |
| F2 | 16 bash hook integration tests | $0 | Every commit |
| F3 | Recorded session replay | $0 | Every commit |
| F4 | Haiku-based smoke tests | ~$0.05 | Prompt changes |
| F5 | Full E2E in Docker | $5-30 | Weekly/pre-release |

CI/CD is configured with three GitHub Actions workflows:
- **PR** — F1 + F2 + F3 on every pull request ($0)
- **Nightly** — F1 through F4 (~$0.05)
- **Weekly** — Full E2E on Sundays ($5-30)

## Design Documents

Detailed design specifications are in `docs/`:

- `rapids-v2-plugin-system-alignment.md` — Plugin structure and Claude Code alignment
- `rapids-v2-feature-coverage-addendum.md` — Claude Code feature integration
- `rapids-v2-testing-strategy-detailed.md` — Multi-layer testing approach

## License

MIT
