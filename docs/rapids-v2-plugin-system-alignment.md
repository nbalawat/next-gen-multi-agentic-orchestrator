# RAPIDS v2 — Alignment with Official Claude Code Plugin System

After reviewing the official Claude Code plugin documentation, several structural changes are needed. The architecture's concepts (phases, scope tiers, Generator-Evaluator, artifacts, audit trail) remain sound. What changes is how RAPIDS packages itself and how domain plugins are structured — we need to conform to the official plugin system rather than inventing our own.

---

## 1. What the Official Plugin System Actually Is

A Claude Code plugin is a directory with this structure:

```
my-plugin/
├── .claude-plugin/
│   └── plugin.json          # Manifest (name is only required field)
├── skills/                  # Auto-discovered. Subdirs with SKILL.md
│   └── my-skill/
│       └── SKILL.md
├── commands/                # Auto-discovered. Markdown files = slash commands
│   └── my-command.md
├── agents/                  # Auto-discovered. Markdown files = subagents
│   └── my-agent.md
├── hooks/                   # Auto-discovered
│   ├── hooks.json           # Hook configuration
│   └── scripts/             # Hook scripts
├── .mcp.json                # MCP server definitions (auto-discovered)
├── .lsp.json                # LSP server definitions (auto-discovered)
├── settings.json            # Default settings for the plugin
└── scripts/                 # Utility scripts
```

Key facts:
- `.claude-plugin/plugin.json` is the manifest. Only `name` is required.
- All component directories (`commands/`, `agents/`, `skills/`, `hooks/`) must be at plugin root, NOT inside `.claude-plugin/`.
- Claude Code auto-discovers components from standard directories — no need to list them in the manifest.
- Plugin skills are namespaced: `my-plugin:my-skill` becomes `/my-plugin:my-skill`.
- Agents support frontmatter: `name`, `description`, `model`, `effort`, `maxTurns`, `tools`, `disallowedTools`, `skills`, `memory`, `background`, `isolation` (only valid value: `"worktree"`).
- Hooks use `hooks.json` format (same as `.claude/settings.json` hook format).
- `${CLAUDE_PLUGIN_ROOT}` is available in hook commands, skill content, agent content for portable paths.
- Plugins are installed via `/plugin install name@marketplace`, `--plugin-dir` flag, or programmatically via the Agent SDK.
- Plugins can be distributed through marketplaces (official Anthropic marketplace or custom).

---

## 2. What Changes in RAPIDS

### 2.1 RAPIDS Itself Becomes a Plugin

RAPIDS core is no longer a loose collection of files in `.claude/`. It is a proper Claude Code plugin that can be installed via `/plugin install rapids@rapids-marketplace` or `--plugin-dir`.

**Before (our custom layout):**
```
project/
├── .claude/
│   ├── commands/rapids/start.md    # Custom commands
│   ├── agents/rapids-lead.md       # Custom agents
│   ├── skills/rapids-core/SKILL.md # Custom skill
│   └── settings.json               # Hook wiring
├── rapids-plugins/                  # Our custom plugin directory
│   ├── rapids-plugin-gcp/
│   └── rapids-plugin-react/
```

**After (official plugin system):**
```
project/
├── .claude/
│   ├── settings.json               # Only enabledPlugins + extraKnownMarketplaces
│   └── agents/                     # Project-specific agents (generated at runtime)
│       ├── impl-F001.md            # Generated per-feature during implementation
│       └── eval-agent.md           # Generated evaluator
```

RAPIDS core and domain plugins are installed as proper plugins:
```
~/.claude/plugins/                   # Or wherever Claude Code stores installed plugins
├── rapids-core@rapids-marketplace/  # Installed via /plugin install
│   ├── .claude-plugin/
│   │   └── plugin.json
│   ├── skills/
│   │   ├── start/SKILL.md          # /rapids-core:start
│   │   ├── status/SKILL.md         # /rapids-core:status
│   │   ├── go/SKILL.md             # /rapids-core:go
│   │   └── export/SKILL.md         # /rapids-core:export
│   ├── agents/
│   │   └── rapids-lead.md          # Lead orchestrator agent
│   ├── hooks/
│   │   ├── hooks.json              # All RAPIDS lifecycle hooks
│   │   └── scripts/
│   │       ├── session-start.sh
│   │       ├── post-tool-use.sh
│   │       ├── stop-check.sh
│   │       ├── pre-compact.sh
│   │       ├── task-completed.sh
│   │       ├── teammate-idle.sh
│   │       └── worktree-create.sh
│   └── scripts/
│       ├── scope-classifier.sh
│       ├── claude-md-generator.sh
│       └── artifact-validator.sh
│
├── rapids-gcp@rapids-marketplace/   # Domain plugin
│   ├── .claude-plugin/
│   │   └── plugin.json
│   ├── skills/
│   │   ├── gcp-architecture/SKILL.md
│   │   ├── terraform-authoring/SKILL.md
│   │   └── gcp-deploy/SKILL.md
│   ├── agents/
│   │   ├── gcp-architect.md
│   │   └── terraform-engineer.md
│   └── hooks/
│       ├── hooks.json
│       └── scripts/
│           └── gcp-worktree-setup.sh
│
└── rapids-react@rapids-marketplace/
    ├── .claude-plugin/
    │   └── plugin.json
    ├── skills/
    │   ├── react-design/SKILL.md
    │   └── react-component/SKILL.md
    └── agents/
        └── react-developer.md
```

### 2.2 Manifest Changes

**Before (our custom `manifest.yaml`):**
```yaml
id: rapids-plugin-gcp
name: GCP Platform
version: 1.0.0
rapids_core_version: ">=1.0.0 <2.0.0"
description: >
  GCP architecture, Terraform, deployment, and monitoring.
capabilities:
  analysis:
    - id: gcp-architecture-design
      description: Generate GCP architecture
  implement:
    - id: terraform-authoring
      description: Write Terraform modules
team_roles:
  implement:
    - name: terraform-engineer
      agent_file: phases/implement/agents/terraform-engineer.md
      worktree_isolation: true
config:
  project_id: { type: string, required: true }
```

**After (official `plugin.json` + RAPIDS metadata in a separate file):**

```json
// .claude-plugin/plugin.json (official Claude Code manifest)
{
  "name": "rapids-gcp",
  "version": "1.0.0",
  "description": "GCP architecture, Terraform, deployment, and monitoring for RAPIDS projects",
  "author": { "name": "Your Org" },
  "keywords": ["rapids", "gcp", "terraform", "cloud-architecture"]
}
```

```json
// rapids.plugin.json (RAPIDS-specific metadata, read by rapids-core plugin)
{
  "rapids_core_version": ">=1.0.0",
  "capabilities": {
    "analysis": [
      { "id": "gcp-architecture-design", "description": "Generate GCP architecture", "depth": ["standard", "deep"] }
    ],
    "implement": [
      { "id": "terraform-authoring", "description": "Write Terraform modules", "depth": ["shallow", "standard", "deep"] }
    ],
    "deploy": [
      { "id": "gcp-deploy", "description": "Deploy via Terraform/gcloud", "depth": ["standard", "deep"] }
    ]
  },
  "config": {
    "project_id": { "type": "string", "required": true },
    "region": { "type": "string", "default": "us-central1" }
  },
  "test_infrastructure": {
    "services": [
      { "name": "bigtable-emulator", "image": "google/cloud-sdk:emulators", "port": 8086 }
    ]
  }
}
```

This way the plugin is a valid Claude Code plugin (discoverable, installable, auto-discovered components), AND it carries RAPIDS-specific metadata that the rapids-core plugin reads for phase routing, capability resolution, etc.

### 2.3 Slash Commands Become Skills

In the official plugin system, skills are the preferred extension mechanism (commands are legacy). Our four RAPIDS commands become skills:

**Before:**
```
.claude/commands/rapids/
├── start.md       # /rapids/start
├── status.md      # /rapids/status
├── go.md          # /rapids/go
└── export.md      # /rapids/export
```

**After:**
```
rapids-core/skills/
├── start/
│   └── SKILL.md   # /rapids-core:start
├── status/
│   └── SKILL.md   # /rapids-core:status
├── go/
│   └── SKILL.md   # /rapids-core:go
└── export/
    └── SKILL.md   # /rapids-core:export
```

The user invokes `/rapids-core:start Build a payment dashboard...` or Claude auto-invokes the skill when it recognizes RAPIDS-relevant context.

**Implementation consideration:** The namespacing (`rapids-core:start` vs `start`) is a trade-off. It's more explicit but more typing. We can mitigate this by making the SKILL.md description broad enough that Claude auto-invokes it when the user says something like "let's start a new project" — so the user rarely needs to type the full namespaced command.

### 2.4 Plugin Phase Overlays Become Skills

**Before (our custom layout):**
```
rapids-plugin-gcp/phases/
├── analysis/prompts/overlay.md
├── plan/prompts/overlay.md
└── implement/prompts/overlay.md
```

**After (official skills):**
```
rapids-gcp/skills/
├── gcp-architecture/
│   └── SKILL.md        # Triggers during analysis phase for GCP projects
├── terraform-planning/
│   └── SKILL.md        # Triggers during plan phase for Terraform specs
├── terraform-authoring/
│   └── SKILL.md        # Triggers during implement phase for Terraform code
└── gcp-deploy/
    └── SKILL.md        # Triggers during deploy phase
```

Each SKILL.md has a `description` field in its frontmatter that determines when Claude activates it. The description must include phase context so Claude only activates it at the right time:

```markdown
---
name: gcp-architecture
description: >
  Use this skill when designing GCP cloud architecture during the RAPIDS
  analysis phase. Activates when the project involves Google Cloud Platform
  services and the current RAPIDS phase is analysis. Provides guidance on
  service selection, IAM design, network topology, and cost estimation.
---

## GCP Architecture Design

When designing GCP architecture for this project, consider:

[... phase overlay content ...]
```

### 2.5 Domain Agents Use Official Frontmatter

**Before (our custom agent definition):**
```markdown
<!-- rapids-plugin-gcp/phases/implement/agents/terraform-engineer.md -->
---
name: gcp:terraform-engineer
isolation: worktree
---
You are implementing Terraform modules...
```

**After (official Claude Code agent frontmatter):**
```markdown
<!-- rapids-gcp/agents/terraform-engineer.md -->
---
name: terraform-engineer
description: Implements Terraform modules from RAPIDS feature specifications. Use for GCP infrastructure implementation during the RAPIDS implement phase.
model: sonnet
effort: medium
maxTurns: 50
isolation: worktree
tools: Read, Write, Edit, Bash, Grep, Glob
disallowedTools: WebFetch
---

You are a Terraform engineer implementing infrastructure modules per the RAPIDS feature specification.

## Your workflow
1. Read the feature spec from .rapids/phases/plan/features/
2. Read the architecture document from .rapids/phases/analysis/
3. Implement the Terraform module incrementally
4. Write tests against the Bigtable emulator
5. Commit after each acceptance criterion passes
6. Update feature-progress.json

## Rules
- One acceptance criterion at a time
- Real tests against emulators, no mocks
- Commit with descriptive messages after each criterion
```

Key changes: `model` and `effort` are now official frontmatter fields. `isolation: worktree` is officially supported. `tools` and `disallowedTools` control what the agent can use. No custom namespacing needed — the plugin namespace handles it.

### 2.6 Hooks Use Official hooks.json Format

**Before (our custom approach — hooks in `.claude/settings.json`):**
```json
{
  "hooks": {
    "SessionStart": [{ "hooks": [{ "type": "command", "command": ".rapids/hooks/session-start.sh" }] }]
  }
}
```

**After (hooks in the plugin's `hooks/hooks.json`):**
```json
{
  "hooks": {
    "SessionStart": [{
      "hooks": [{
        "type": "command",
        "command": "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/session-start.sh"
      }]
    }],
    "PostToolUse": [{
      "matcher": "Write|Edit|Bash",
      "hooks": [{
        "type": "command",
        "command": "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-tool-use.sh"
      }]
    }],
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/stop-check.sh"
      }]
    }],
    "PreCompact": [{
      "hooks": [{
        "type": "command",
        "command": "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/pre-compact.sh"
      }]
    }],
    "TaskCompleted": [{
      "hooks": [{
        "type": "command",
        "command": "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/task-completed.sh"
      }]
    }],
    "TeammateIdle": [{
      "hooks": [{
        "type": "command",
        "command": "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/teammate-idle.sh"
      }]
    }],
    "WorktreeCreate": [{
      "hooks": [{
        "type": "command",
        "command": "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/worktree-create.sh"
      }]
    }]
  }
}
```

The `${CLAUDE_PLUGIN_ROOT}` variable makes paths portable — the hooks work regardless of where the plugin is installed. Domain plugins can add their own hooks.json that merges with the core hooks (hooks from all installed plugins fire for their matching events).

### 2.7 Plugin Installation & Distribution

RAPIDS plugins are distributed through a RAPIDS marketplace:

```json
// rapids-marketplace/marketplace.json
{
  "name": "rapids-marketplace",
  "description": "RAPIDS orchestration plugins for AI-assisted software delivery",
  "plugins": {
    "rapids-core": {
      "description": "Core RAPIDS orchestration engine",
      "source": { "type": "git", "url": "https://github.com/your-org/rapids-core" }
    },
    "rapids-gcp": {
      "description": "GCP architecture, Terraform, and deployment",
      "source": { "type": "git", "url": "https://github.com/your-org/rapids-gcp" }
    },
    "rapids-react": {
      "description": "React frontend design and implementation",
      "source": { "type": "git", "url": "https://github.com/your-org/rapids-react" }
    }
  }
}
```

**User installation flow:**
```bash
# One-time: add the RAPIDS marketplace
# (via /plugin command in Claude Code)
/plugin marketplace add your-org/rapids-marketplace

# Install core + domain plugins
/plugin install rapids-core@rapids-marketplace
/plugin install rapids-gcp@rapids-marketplace
/plugin install rapids-react@rapids-marketplace
```

Or for a project, the RAPIDS core's `/rapids-core:start` skill can auto-detect needed domain plugins and prompt the user to install them.

---

## 3. Revised Plugin Structure (Official-Compliant)

### 3.1 rapids-core Plugin

```
rapids-core/
├── .claude-plugin/
│   └── plugin.json
│       {
│         "name": "rapids-core",
│         "version": "1.0.0",
│         "description": "RAPIDS orchestration engine — structured AI-assisted software delivery through Research, Analysis, Plan, Implement, Deploy, and Sustain phases"
│       }
│
├── skills/
│   ├── start/
│   │   └── SKILL.md               # /rapids-core:start — onboard + scope + begin
│   ├── status/
│   │   └── SKILL.md               # /rapids-core:status — phase, progress, cost
│   ├── go/
│   │   └── SKILL.md               # /rapids-core:go — advance / continue
│   └── export/
│       └── SKILL.md               # /rapids-core:export — client docs
│
├── agents/
│   └── rapids-lead.md             # Lead orchestrator agent
│
├── hooks/
│   ├── hooks.json                 # All core lifecycle hooks
│   └── scripts/
│       ├── session-start.sh       # Context load, CLAUDE.md generation, resume
│       ├── post-tool-use.sh       # Audit logging, cost tracking, artifact validation
│       ├── stop-check.sh          # Phase completion, state save
│       ├── pre-compact.sh         # Context preservation
│       ├── task-completed.sh      # Acceptance criteria, dep graph update
│       ├── teammate-idle.sh       # Next task assignment
│       └── worktree-create.sh     # Plugin-specific worktree setup
│
├── scripts/
│   ├── scope-classifier.sh        # Tier classification logic
│   ├── claude-md-generator.sh     # Dynamic CLAUDE.md composition
│   ├── artifact-validator.sh      # Schema validation
│   ├── wave-computer.sh           # Dependency graph → implementation waves
│   └── cost-tracker.sh            # Token/cost aggregation
│
├── schemas/                        # Artifact type schemas
│   ├── feature-spec.xsd
│   ├── dependency-graph.schema.json
│   └── journal-entry.schema.json
│
├── templates/                      # Phase artifact templates
│   ├── research/
│   │   └── problem-statement.md
│   ├── analysis/
│   │   ├── solution-design.md
│   │   └── adr-template.md
│   ├── plan/
│   │   └── feature-spec-template.xml
│   └── implement/
│       ├── feature-progress-template.json
│       └── evaluator-prompt.md
│
└── settings.json                   # Default settings (env vars, etc.)
```

### 3.2 Domain Plugin (e.g., rapids-gcp)

```
rapids-gcp/
├── .claude-plugin/
│   └── plugin.json
│       {
│         "name": "rapids-gcp",
│         "version": "1.0.0",
│         "description": "GCP architecture, Terraform, and deployment for RAPIDS"
│       }
│
├── rapids.plugin.json              # RAPIDS-specific metadata (capabilities, config, test infra)
│
├── skills/
│   ├── gcp-architecture/
│   │   └── SKILL.md               # Analysis phase: GCP architecture design
│   ├── terraform-planning/
│   │   └── SKILL.md               # Plan phase: Terraform spec generation
│   ├── terraform-authoring/
│   │   └── SKILL.md               # Implement phase: write Terraform modules
│   ├── gcp-deploy/
│   │   └── SKILL.md               # Deploy phase: Terraform apply + Cloud Run
│   └── cloud-monitoring/
│       └── SKILL.md               # Sustain phase: monitoring setup
│
├── agents/
│   ├── gcp-architect.md            # Analysis phase teammate
│   └── terraform-engineer.md       # Implement phase coder (worktree-isolated)
│
├── hooks/
│   ├── hooks.json                  # GCP-specific hooks (worktree setup)
│   └── scripts/
│       └── gcp-worktree-setup.sh   # Start emulators, set env vars
│
├── templates/
│   ├── gcp-architecture.md         # Architecture doc template
│   └── terraform-module.tf         # Terraform scaffold
│
└── evals/                          # Quality assurance
    ├── trigger-evals.json          # Does skill fire at right time?
    └── quality-evals.yaml          # Is output good?
```

### 3.3 Minimum Viable Domain Plugin (3 files)

```
rapids-my-domain/
├── .claude-plugin/
│   └── plugin.json                 # { "name": "rapids-my-domain", "version": "1.0.0", "description": "..." }
├── rapids.plugin.json              # { "capabilities": { "implement": [{ "id": "...", "description": "..." }] } }
└── skills/
    └── my-domain-implement/
        └── SKILL.md                # Implementation guidance for this domain
```

---

## 4. What Stays the Same

The official plugin system changes the packaging, not the architecture. These elements are unchanged:

| Component | Status |
|-----------|--------|
| Scope tiers (1-5) | Unchanged |
| Phase routing (data-driven) | Unchanged |
| `.rapids/` directory (artifacts, audit, context) | Unchanged — this is project state, not plugin structure |
| `rapids.json` (single config file) | Unchanged |
| Generator-Evaluator architecture | Unchanged |
| Wave-based implementation | Unchanged |
| Git worktrees for feature isolation | Unchanged — `isolation: worktree` is officially supported |
| Model right-sizing | Unchanged — `model` and `effort` are official agent frontmatter fields |
| Cost tracking via PostToolUse hook | Unchanged |
| Context preservation via PreCompact | Unchanged |
| Artifact schemas and validation | Unchanged |
| Testing pyramid | Unchanged |
| Export package for clients | Unchanged |

---

## 5. Impact on Consolidated Implementation Considerations

The following sections of the consolidated document need updates:

### Part 4 (Plugin System)

**Section 4.2:** Minimum viable plugin is now 3 files (plugin.json + rapids.plugin.json + one SKILL.md), not 4.

**Section 4.3:** Full plugin structure uses official directories (`skills/`, `agents/`, `hooks/`, `.mcp.json`) instead of our custom `phases/` directory with prompt overlays. Phase-specific guidance is now delivered through skills with phase-aware descriptions.

**Section 4.4:** Manifest is split: `plugin.json` (official, minimal) + `rapids.plugin.json` (RAPIDS-specific capabilities, config, test infrastructure).

**Section 4.8:** Plugin composition now relies on the official hook merging (all hooks fire for matching events) and skill namespacing (no manual conflict resolution needed for skill names).

### Part 9 (Claude Code Integration Points)

**Section 9.1:** Slash commands are now skills. User types `/rapids-core:start` or Claude auto-invokes based on context.

**Section 9.2:** Hooks are in the plugin's `hooks/hooks.json`, not in `.claude/settings.json`. Use `${CLAUDE_PLUGIN_ROOT}` for portable paths.

**Section 9.5:** Skills are the primary extension mechanism. Each domain plugin's per-phase guidance is a skill with a phase-aware description.

### Part 12 (Build Sequence)

**Wave 1 addition:** Set up the RAPIDS marketplace structure (marketplace.json + git repo) alongside the core plugin. Build the plugin scaffold generator.

### Part 13 (File System Reference)

**Section 13.1:** The `.claude/` directory is much thinner. Only `settings.json` (with enabledPlugins) and `agents/` (for runtime-generated per-feature agents) live there. Everything else is in installed plugins and `.rapids/`.

---

## 6. Updated Project Layout (At Rest)

```
project-root/
├── .claude/
│   ├── settings.json               # enabledPlugins, extraKnownMarketplaces
│   └── agents/                     # Runtime-generated agents (implementation phase)
│
├── CLAUDE.md                       # Dynamically generated per phase by rapids-core hook
│
├── .rapids/                        # Project state (unchanged)
│   ├── rapids.json                 # THE one config file
│   ├── audit/
│   │   ├── timeline.jsonl
│   │   └── cost.jsonl
│   ├── phases/
│   │   ├── analysis/
│   │   ├── plan/
│   │   ├── implement/
│   │   └── deploy/
│   └── context/
│       └── accumulated.json
│
├── src/                            # Your code
├── tests/
└── .gitignore
```

Plugins are installed globally or per-user (in `~/.claude/plugins/`), not in the project directory. The project only contains `.rapids/` (state) and `.claude/` (thin config + runtime agents). This is a cleaner separation: plugins are tools, `.rapids/` is project state.

---

## 7. Updated Installation Flow

```
# First time setting up RAPIDS (one-time per developer machine)
/plugin marketplace add your-org/rapids-marketplace
/plugin install rapids-core@rapids-marketplace

# Starting a new project (rapids-core auto-detects and suggests domain plugins)
cd ~/projects/my-new-project
claude
> /rapids-core:start Build a payment reconciliation dashboard on GCP with React

# rapids-core detects GCP + React, prompts:
# "This project uses GCP and React. I recommend installing:
#  - rapids-gcp (Terraform, Cloud Run, Bigtable)
#  - rapids-react (component design, frontend implementation)
#  Install these now?"

# User confirms → plugins installed → onboarding continues
```
