---
name: go
description: >
  Use this skill to advance the RAPIDS project to the next phase or continue
  work in the current phase. Activates when the user says "go", "continue",
  "proceed", "next phase", or invokes /rapids-core:go. Handles phase gate
  verification, phase transitions, and wave execution.
---

# RAPIDS Phase Advancement

**IMPORTANT:** At every decision point in this flow, you MUST use the `AskUserQuestion`
tool to collect user input. Do NOT simply print questions — call the tool so the user
gets a structured prompt with selectable options.

---

## Step 1: Check Current State & Display Phase Banner

Read `.rapids/rapids.json` to determine:
- Current phase
- Next phase in the sequence
- Whether phase gate conditions are met

Display the current phase banner with activity context:
```bash
python3 -c "
import json
from pathlib import Path
from rapids_core.ascii_art import phase_banner
from rapids_core.phase_router import route_phases

config = json.loads(Path('.rapids/rapids.json').read_text())
phase = config.get('current', {}).get('phase', 'unknown')
tier = config.get('scope', {}).get('tier', 0)
project_id = config.get('project', {}).get('id', 'unknown')
phases = route_phases(tier)

print(phase_banner(
    current_phase=phase,
    activity='Checking phase gate conditions...',
    tier=tier,
    project_name=project_id,
    phases_in_scope=phases,
))
"
```

## Step 2: Phase Gate Verification

Before advancing, verify the current phase's deliverables exist:

| Phase | Required Artifacts |
|-------|-------------------|
| research | problem-statement.md |
| analysis | solution-design.md, at least one ADR |
| plan | feature specs (XML), dependency-graph.json |
| implement | all features pass evaluator, tests pass |
| deploy | deployment verified, smoke tests pass |

If artifacts are missing, inform the user what's needed before advancing.

## Step 3: Confirm Phase Transition (AskUserQuestion)

Before transitioning, use `AskUserQuestion` to confirm with the user:

```json
{
  "questions": [
    {
      "question": "Phase gate passed. Ready to advance from <current> to <next>. Proceed?",
      "header": "Advance",
      "multiSelect": false,
      "options": [
        {
          "label": "Advance to <next_phase> (Recommended)",
          "description": "All gate conditions met. Move to the next phase."
        },
        {
          "label": "Stay in current phase",
          "description": "Continue working in <current_phase> before advancing"
        },
        {
          "label": "Skip to a different phase",
          "description": "Jump to a specific phase (e.g., skip analysis for a quick prototype)"
        }
      ]
    }
  ]
}
```

## Step 4: Phase Transition

When transitioning, display the transition banner:
```bash
python3 -c "
from rapids_core.ascii_art import transition_banner
print(transition_banner(
    from_phase='<current_phase>',
    to_phase='<next_phase>',
    project_name='<project_id>',
))
"
```

Update `rapids.json` with the new phase, regenerate `CLAUDE.md`:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/claude-md-generator.sh .
```

Update the project registry with the new phase:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/project-registry.sh update-phase "$(pwd)" "<new_phase>"
```

### Step 4b: Scaffold Phase Artifacts from Templates

When entering a new phase, copy the relevant templates from
`${CLAUDE_PLUGIN_ROOT}/templates/<phase>/` into `.rapids/phases/<phase>/`
if they don't already exist. This ensures each phase starts with proper
artifact skeletons:

| Entering Phase | Templates to Copy |
|---------------|-------------------|
| research | `research/problem-statement.md` |
| analysis | `analysis/solution-design.md`, `analysis/adr-template.md` |
| plan | `plan/feature-spec-template.xml` |
| implement | `implement/evaluator-prompt.md`, `implement/feature-progress-template.json` |

```bash
# Example for analysis phase:
TMPL_DIR="${CLAUDE_PLUGIN_ROOT}/templates/<phase>"
DEST_DIR=".rapids/phases/<phase>"
mkdir -p "$DEST_DIR"
for tmpl in "$TMPL_DIR"/*; do
  dest="$DEST_DIR/$(basename "$tmpl")"
  [ -f "$dest" ] || cp "$tmpl" "$dest"
done
```

Only copy templates — never overwrite existing artifacts that may contain
work from a previous attempt or manual edits.

## Step 5: Display New Phase Banner

After transitioning, show the new phase banner with the upcoming activity:
```bash
python3 -c "
import json
from pathlib import Path
from rapids_core.ascii_art import phase_banner
from rapids_core.phase_router import route_phases

config = json.loads(Path('.rapids/rapids.json').read_text())
phase = config.get('current', {}).get('phase', 'unknown')
tier = config.get('scope', {}).get('tier', 0)
project_id = config.get('project', {}).get('id', 'unknown')
phases = route_phases(tier)

print(phase_banner(
    current_phase=phase,
    activity='<describe what will happen in this phase>',
    tier=tier,
    project_name=project_id,
    phases_in_scope=phases,
))
"
```

## Step 6: Phase-Specific Execution

### If entering IMPLEMENT phase:

1. **Generate dependency graph** from feature spec XMLs:
   ```bash
   python3 -c "
   from rapids_core.ascii_art import activity_banner
   print(activity_banner('implement', 'Generating dependency graph from feature specs...'))
   "
   ```

   If `.rapids/phases/plan/dependency-graph.json` does not already exist, generate it
   from the feature spec XMLs in the plan directory:
   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/dependency-graph-generator.sh .rapids/phases/plan \
     > .rapids/phases/plan/dependency-graph.json
   ```

   Then validate the generated graph:
   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/artifact-validator.sh .rapids/phases/plan/dependency-graph.json
   ```

2. **Compute implementation waves**:
   ```bash
   python3 -c "
   from rapids_core.ascii_art import activity_banner
   print(activity_banner('implement', 'Computing implementation waves from dependency graph...'))
   "
   ```

   ```bash
   cat .rapids/phases/plan/dependency-graph.json | ${CLAUDE_PLUGIN_ROOT}/scripts/wave-computer.sh
   ```

3. **Confirm wave plan with user (AskUserQuestion):**

   Use `AskUserQuestion` to let the user review the wave plan before execution:
   ```json
   {
     "questions": [
       {
         "question": "Wave plan computed: N waves, M total features. How should we proceed?",
         "header": "Wave plan",
         "multiSelect": false,
         "options": [
           {
             "label": "Execute all waves (Recommended)",
             "description": "Run all waves sequentially with the configured execution mode"
           },
           {
             "label": "Execute wave by wave",
             "description": "Pause for approval between each wave"
           },
           {
             "label": "Execute single wave",
             "description": "Run only Wave 1, then stop for review"
           }
         ]
       }
     ]
   }
   ```

4. **Per-wave dispatch decision and execution:**

   For each wave, determine the execution method and dispatch:

   ```bash
   python3 -c "
   import json
   from pathlib import Path
   from rapids_core.wave_executor import choose_execution_method

   graph = json.loads(Path('.rapids/phases/plan/dependency-graph.json').read_text())
   metadata = graph.get('metadata', {})
   feature_plugins = {fid: m.get('plugin', '') for fid, m in metadata.items()}

   config = json.loads(Path('.rapids/rapids.json').read_text())
   tier = config.get('scope', {}).get('tier', 3)

   wave_features = <current_wave_features>
   method = choose_execution_method(wave_features, graph, tier, feature_plugins)
   print(method)
   "
   ```

   **If method is `"batch"` → Use Batch Dispatcher:**

   ```bash
   python3 -c "
   from rapids_core.ascii_art import activity_banner
   print(activity_banner('implement', 'Wave N — Dispatching N features via /batch (parallel execution)'))
   "
   ```

   Generate the batch dispatch plan:
   ```bash
   echo '<dispatch_config_json>' | ${CLAUDE_PLUGIN_ROOT}/scripts/batch-dispatcher.sh
   ```

   The dispatch config JSON should include:
   ```json
   {
     "wave_number": N,
     "wave_features": ["F001", "F003"],
     "feature_specs": {"F001": "<xml>...", "F003": "<xml>..."},
     "feature_plugins": {"F001": "rapids-gcp", "F003": ""},
     "accumulated_context": <contents of .rapids/context/accumulated.json>,
     "evaluator_template": "<contents of evaluator-prompt.md>",
     "project_id": "<project_id>"
   }
   ```

   Use `AskUserQuestion` to confirm the batch plan, then invoke `/batch` with
   the formatted prompts from the dispatch plan.

   **If method is `"agent_teams"` → Use Agent Team Orchestrator:**

   ```bash
   python3 -c "
   from rapids_core.ascii_art import activity_banner
   print(activity_banner('implement', 'Wave N — Assembling agent team for N coordinated features'))
   "
   ```

   Generate the agent team plan:
   ```bash
   echo '<orchestrator_config_json>' | ${CLAUDE_PLUGIN_ROOT}/scripts/agent-team-orchestrator.sh
   ```

   The orchestrator config JSON should include:
   ```json
   {
     "wave_number": N,
     "wave_features": ["F001", "F002"],
     "feature_specs": {"F001": "<xml>...", "F002": "<xml>..."},
     "feature_plugins": {"F001": "rapids-gcp", "F002": "rapids-react"},
     "available_agents": [<parsed agent definitions from plugin agent/ directories>],
     "dependency_graph": <full dependency graph>,
     "accumulated_context": <contents of .rapids/context/accumulated.json>,
     "evaluator_template": "<contents of evaluator-prompt.md>",
     "project_id": "<project_id>",
     "max_retries": 3
   }
   ```

   Use `AskUserQuestion` to confirm the team plan, then use the `Agent` tool to
   spawn the lead agent (`rapids-lead`) with the full plan. The lead agent will:
   - Spawn generator agents per the assignments (each in a worktree)
   - Monitor progress via feature-progress JSON files
   - Run evaluators after each feature completes
   - Handle retries and escalation

5. **For each feature (within batch or agent team)**, display activity banners:
   ```bash
   python3 -c "
   from rapids_core.ascii_art import activity_banner
   print(activity_banner('implement', 'Wave N — Feature FXXX: <feature_name>\nCriterion: <current_criterion>'))
   "
   ```

   - Generator implements incrementally (one criterion at a time)
   - `/simplify` runs on changed files (3 parallel review agents)
   - Evaluator verifies independently
   - If pass → merge; if fail → feedback to Generator (max 3 retries)

7. **At wave boundaries (AskUserQuestion):**

   When a wave completes and Hybrid or Wave-by-wave mode is active, use
   `AskUserQuestion` to get approval:
   ```json
   {
     "questions": [
       {
         "question": "Wave N complete (X/Y features passed). Ready to start Wave N+1?",
         "header": "Next wave",
         "multiSelect": false,
         "options": [
           {
             "label": "Start Wave N+1 (Recommended)",
             "description": "All features in Wave N passed. Proceed to the next wave."
           },
           {
             "label": "Review Wave N results first",
             "description": "Show detailed results before continuing"
           },
           {
             "label": "Stop here",
             "description": "Pause execution. Resume later with /rapids-core:go"
           }
         ]
       }
     ]
   }
   ```

8. **On evaluator failure (AskUserQuestion):**

   When the evaluator rejects a feature after max retries, use `AskUserQuestion`:
   ```json
   {
     "questions": [
       {
         "question": "Feature FXXX failed evaluation after 3 attempts. How should we proceed?",
         "header": "Failed",
         "multiSelect": false,
         "options": [
           {
             "label": "Retry with different approach",
             "description": "Generator will attempt the feature with a fresh strategy"
           },
           {
             "label": "Skip and continue",
             "description": "Skip this feature and proceed with the next one in the wave"
           },
           {
             "label": "Stop for manual intervention",
             "description": "Pause execution so you can investigate and fix manually"
           }
         ]
       }
     ]
   }
   ```

9. **Permission model:**
   - Autonomous mode → enable auto mode (`--enable-auto-mode`)
   - Human-in-the-loop → standard approval (Tier 4-5, client envs)
   - Hybrid (recommended) → auto mode within waves, manual at wave boundaries

10. **Monitoring (autonomous mode):**
   - Set up progress polling: `/loop 5m "check feature progress"`
   - Suggest Remote Control for mobile monitoring
   - Use `/btw` for side questions without disrupting work

### If entering DEPLOY phase:

1. Display activity banner:
   ```bash
   python3 -c "
   from rapids_core.ascii_art import activity_banner
   print(activity_banner('deploy', 'Deploying application and running smoke tests...'))
   "
   ```

2. **Confirm deployment target (AskUserQuestion):**
   ```json
   {
     "questions": [
       {
         "question": "Ready to deploy. Which environment should we target?",
         "header": "Deploy to",
         "multiSelect": false,
         "options": [
           {
             "label": "Staging (Recommended)",
             "description": "Deploy to staging environment for verification first"
           },
           {
             "label": "Production",
             "description": "Deploy directly to production"
           },
           {
             "label": "Local / Docker",
             "description": "Deploy locally for smoke testing"
           }
         ]
       }
     ]
   }
   ```

3. Prefer event-driven execution via Channels over polling
4. CI/CD events push "build complete" → RAPIDS reacts
5. Run smoke tests after deployment

### If entering RESEARCH or ANALYSIS phase:

Use `AskUserQuestion` to confirm the approach:
```json
{
  "questions": [
    {
      "question": "Entering <phase>. What areas should we focus on?",
      "header": "Focus",
      "multiSelect": true,
      "options": [
        {
          "label": "Domain research",
          "description": "Explore the problem domain, existing solutions, and best practices"
        },
        {
          "label": "Technical constraints",
          "description": "Identify infrastructure, performance, and compliance constraints"
        },
        {
          "label": "Stakeholder requirements",
          "description": "Clarify user needs, business rules, and acceptance criteria"
        },
        {
          "label": "Risk assessment",
          "description": "Identify technical risks and potential blockers"
        }
      ]
    }
  ]
}
```

## Rules
- **MUST use `AskUserQuestion` tool** at every decision point — never just print questions
- Always display the phase banner before starting work so the user knows exactly where they are
- Always display the transition banner when moving between phases
- Always show the activity banner before each major action (wave start, feature start)
- Always confirm phase transitions with the user before advancing
- At wave boundaries in hybrid/wave-by-wave mode, always ask before proceeding
- On evaluator failures, always ask the user how to proceed
- In autonomous mode, AskUserQuestion is skipped for wave boundaries (but still used for failures)
- Log all phase transitions to timeline.jsonl
- Update the project registry on every phase change
