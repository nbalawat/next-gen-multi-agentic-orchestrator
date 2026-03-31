---
name: start
description: >
  Use this skill to begin a new RAPIDS project. Activates when the user describes
  a software project to build, asks to "start a new project", "build something",
  or invokes /rapids-core:start. Handles onboarding, scope classification,
  plugin detection, project registration, and .rapids/ directory initialization.
---

# RAPIDS Project Onboarding

You are starting a new RAPIDS project. Follow these steps exactly.

**IMPORTANT:** At each decision point below, you MUST use the `AskUserQuestion` tool
to collect user input. Do NOT simply print a question — call the tool so the user
gets a structured prompt with selectable options.

---

## Step 0: Display Welcome Banner & Active Projects

First, show the RAPIDS welcome banner with all active managed projects:
```bash
python3 -c "
from rapids_core.ascii_art import welcome_banner
from rapids_core.project_registry import list_projects
projects = list_projects()
print(welcome_banner(projects))
"
```

Display this banner output to the user so they can see what projects are already under RAPIDS management.

## Step 1: Ask for Workspace (AskUserQuestion)

Use the `AskUserQuestion` tool to ask the user which workspace this project belongs to.
A workspace is a parent directory that contains multiple RAPIDS projects.

Generate the payload:
```bash
python3 -c "
import json
from rapids_core.onboarding import workspace_question
from rapids_core.project_registry import list_workspaces
workspaces = list_workspaces()
print(json.dumps(workspace_question(workspaces), indent=2))
"
```

Call `AskUserQuestion` with the generated payload. Based on the response:
- If they selected an existing workspace → use that workspace path
- If they chose "Create new workspace" → they type the path in "Other"; create it and
  register it via `project-registry.sh register-workspace`
- If they chose "No workspace" → the project is standalone (no workspace association)

## Step 2: Ask for Working Directory (AskUserQuestion)

Use the `AskUserQuestion` tool to ask the user for the project working directory.

Call `AskUserQuestion` with these parameters:
```json
{
  "questions": [
    {
      "question": "What is the working directory for this project?",
      "header": "Directory",
      "multiSelect": false,
      "options": [
        {
          "label": "Current directory (Recommended)",
          "description": "Use the current directory: <current_working_directory>"
        },
        {
          "label": "Existing directory",
          "description": "Provide a path to an existing project directory"
        },
        {
          "label": "Create new directory",
          "description": "Specify a path and RAPIDS will create it for you"
        }
      ]
    }
  ]
}
```

You can generate this payload programmatically:
```bash
python3 -c "
import json
from rapids_core.onboarding import working_directory_question
print(json.dumps(working_directory_question('$(pwd)'), indent=2))
"
```

**After the user responds:**
- If they chose "Current directory" → use the current working directory
- If they chose "Existing directory" → they will type the path in the "Other" field; resolve it to absolute
- If they chose "Create new directory" → they will type the path; create it with `mkdir -p`
- Once confirmed, `cd` into that directory for all subsequent operations

## Step 3: Ask What to Build (AskUserQuestion)

If the user hasn't already described their project, use `AskUserQuestion` to ask:

```json
{
  "questions": [
    {
      "question": "What would you like to build? Describe your project briefly.",
      "header": "Project",
      "multiSelect": false,
      "options": [
        {
          "label": "New application",
          "description": "Build a new application or service from scratch"
        },
        {
          "label": "New feature",
          "description": "Add a feature to an existing codebase"
        },
        {
          "label": "Bug fix",
          "description": "Fix a specific bug or issue"
        },
        {
          "label": "Refactor / migration",
          "description": "Refactor code, migrate infrastructure, or upgrade dependencies"
        }
      ]
    }
  ]
}
```

The user will select a category or type a custom description in "Other". Use their
response plus any earlier project description to identify:
- What they want to build
- Target platforms and technologies
- Any constraints mentioned (budget, timeline, compliance)

## Step 4: Classify Scope

Run the scope classifier to determine the project tier (1-5):
```bash
echo '<signals_json>' | ${CLAUDE_PLUGIN_ROOT}/scripts/scope-classifier.sh
```

**Scope signals to extract:**
- `files_impacted`: Estimated number of files that will be created or modified
- `new_infrastructure`: Whether new infrastructure (cloud resources, databases) is needed
- `integrations`: List of external systems/services involved
- `domain_complexity`: "low", "moderate", or "high"

## Step 5: Confirm Scope with User (AskUserQuestion)

**Always confirm scope classification with the user.** Use `AskUserQuestion` with a
preview showing the classification details:

```json
{
  "questions": [
    {
      "question": "RAPIDS classified this as Tier N (Label). Phases: X → Y → Z. Does this look right?",
      "header": "Scope",
      "multiSelect": false,
      "options": [
        {
          "label": "Tier N — Label (Recommended)",
          "description": "Proceed with N phases: X → Y → Z. ~M files, K integration(s).",
          "preview": "<scope preview box — see onboarding.py>"
        },
        {
          "label": "Adjust tier up",
          "description": "This project is more complex than estimated — bump the tier higher",
          "preview": "<adjustment preview — see onboarding.py>"
        },
        {
          "label": "Adjust tier down",
          "description": "This project is simpler than estimated — lower the tier",
          "preview": "<adjustment preview — see onboarding.py>"
        }
      ]
    }
  ]
}
```

Generate this payload programmatically:
```bash
python3 -c "
import json
from rapids_core.onboarding import scope_confirmation_question
print(json.dumps(scope_confirmation_question(
    tier=<tier>, tier_label='<label>',
    phases=<phases_list>,
    files_impacted=<count>,
    integrations=<integrations_list>,
), indent=2))
"
```

**After the user responds:**
- If they confirmed → proceed with the classified tier
- If they chose "Adjust tier up/down" → re-run phase routing with the adjusted tier

## Step 6: Choose Execution Mode (AskUserQuestion)

Use `AskUserQuestion` to let the user pick an execution mode. The recommended
option depends on the tier:

```json
{
  "questions": [
    {
      "question": "Which execution mode should RAPIDS use for this project?",
      "header": "Exec mode",
      "multiSelect": false,
      "options": [
        {
          "label": "Autonomous (Recommended)",
          "description": "RAPIDS runs end-to-end with auto permissions. Best for Tier 1-2."
        },
        {
          "label": "Hybrid",
          "description": "Auto mode within waves, manual approval at wave boundaries. Best for Tier 3."
        },
        {
          "label": "Human-in-the-loop",
          "description": "Manual approval for every major action. Best for Tier 4-5."
        }
      ]
    }
  ]
}
```

Generate programmatically:
```bash
python3 -c "
import json
from rapids_core.onboarding import execution_mode_question
print(json.dumps(execution_mode_question(<tier>), indent=2))
"
```

The recommended option is automatically moved to the first position based on tier.

## Step 7: Detect Domain Plugins

Based on the technologies identified, suggest installing relevant domain plugins:
- GCP/Terraform/Cloud Run → `rapids-gcp`
- React/Next.js frontend → `rapids-react`
- Python/FastAPI backend → `rapids-python`

## Step 8: Initialize Project Structure

Create the `.rapids/` directory with all required subdirectories:
```
.rapids/
├── rapids.json          # Project config (tier, phases, plugins, current state)
├── audit/
│   ├── cost.jsonl       # Cost tracking
│   └── timeline.jsonl   # Event timeline
├── phases/              # Phase artifacts go here
│   ├── research/
│   ├── analysis/
│   ├── plan/
│   ├── implement/
│   ├── deploy/
│   └── sustain/
└── context/
    └── accumulated.json # Accumulated decisions and context
```

### Step 8b: Copy Phase Templates into Artifact Directories

Based on the project tier and the phases that will execute, copy the appropriate
templates from `${CLAUDE_PLUGIN_ROOT}/templates/` into the corresponding
`.rapids/phases/<phase>/` directories. This gives users a starting skeleton
for each deliverable:

| Phase | Template Source | Destination |
|-------|---------------|-------------|
| research | `${CLAUDE_PLUGIN_ROOT}/templates/research/problem-statement.md` | `.rapids/phases/research/problem-statement.md` |
| analysis | `${CLAUDE_PLUGIN_ROOT}/templates/analysis/solution-design.md` | `.rapids/phases/analysis/solution-design.md` |
| analysis | `${CLAUDE_PLUGIN_ROOT}/templates/analysis/adr-template.md` | `.rapids/phases/analysis/adr-template.md` |
| plan | `${CLAUDE_PLUGIN_ROOT}/templates/plan/feature-spec-template.xml` | `.rapids/phases/plan/feature-spec-template.xml` |
| implement | `${CLAUDE_PLUGIN_ROOT}/templates/implement/evaluator-prompt.md` | `.rapids/phases/implement/evaluator-prompt.md` |
| implement | `${CLAUDE_PLUGIN_ROOT}/templates/implement/feature-progress-template.json` | `.rapids/phases/implement/feature-progress-template.json` |

Only copy templates for phases that are in scope for this tier. For example,
Tier 1 (bug fix) only needs implement templates; Tier 5 (platform) gets all of them.

## Step 9: Register Project

Register the project in the central RAPIDS project registry so it can be tracked
across sessions. Include the workspace path if one was selected:
```bash
echo '{"name":"<project_id>","path":"<absolute_working_dir>","workspace":"<workspace_path_or_null>","tier":<tier>,"phase":"<first_phase>","plugins":["<plugin1>"]}' \
  | ${CLAUDE_PLUGIN_ROOT}/scripts/project-registry.sh register
```

## Step 10: Generate CLAUDE.md

Run the CLAUDE.md generator for the first phase:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/claude-md-generator.sh .
```

## Step 11: Display Phase Banner & Present Summary

Display the phase banner showing exactly where we are:
```bash
echo '{"phase":"<first_phase>","activity":"Project initialized — ready to begin","tier":<tier>,"project_name":"<project_id>","phases_in_scope":["<phase1>","<phase2>"]}' \
  | ${CLAUDE_PLUGIN_ROOT}/scripts/ascii-banner.sh phase
```

Tell the user:
- Project tier and what that means
- Which phases will execute (shown visually in the banner)
- Active plugins
- Execution mode selected
- Templates that have been scaffolded into `.rapids/phases/`
- Next step: run `/rapids-core:go` to begin the first phase

## Rules
- **MUST use `AskUserQuestion` tool** for Steps 1, 2, 3, 5, and 6 — never just print the question
- For Tier 4-5, the recommended execution mode is Human-in-the-loop
- For Tier 1-2, the recommended execution mode is Autonomous
- Always register the project in the central registry
- Always copy templates for in-scope phases so artifacts have a starting skeleton
