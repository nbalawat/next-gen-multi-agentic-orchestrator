---
name: start
description: >
  Use this skill to begin a new RAPIDS project. Activates when the user describes
  a software project to build, asks to "start a new project", "build something",
  or invokes /rapids-core:start. Handles onboarding, scope classification,
  plugin detection, and .rapids/ directory initialization.
---

# RAPIDS Project Onboarding

You are starting a new RAPIDS project. Follow these steps:

## Step 1: Understand the Request
Read the user's project description carefully. Identify:
- What they want to build
- Target platforms and technologies
- Any constraints mentioned (budget, timeline, compliance)

## Step 2: Classify Scope
Run the scope classifier to determine the project tier (1-5):
```bash
echo '<signals_json>' | ${CLAUDE_PLUGIN_ROOT}/scripts/scope-classifier.sh
```

**Scope signals to extract:**
- `files_impacted`: Estimated number of files that will be created or modified
- `new_infrastructure`: Whether new infrastructure (cloud resources, databases) is needed
- `integrations`: List of external systems/services involved
- `domain_complexity`: "low", "moderate", or "high"

## Step 3: Detect Domain Plugins
Based on the technologies identified, suggest installing relevant domain plugins:
- GCP/Terraform/Cloud Run → `rapids-gcp`
- React/Next.js frontend → `rapids-react`
- Python/FastAPI backend → `rapids-python`

## Step 4: Initialize Project Structure
Create the `.rapids/` directory:
```
.rapids/
├── rapids.json          # Project config (tier, phases, plugins, current state)
├── audit/
│   ├── cost.jsonl       # Cost tracking
│   └── timeline.jsonl   # Event timeline
├── phases/              # Phase artifacts go here
│   ├── analysis/
│   ├── plan/
│   └── implement/
└── context/
    └── accumulated.json # Accumulated decisions and context
```

## Step 5: Generate CLAUDE.md
Run the CLAUDE.md generator for the first phase:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/claude-md-generator.sh .
```

## Step 6: Present Summary
Tell the user:
- Project tier and what that means
- Which phases will execute
- Active plugins
- Next step: run `/rapids-core:go` to begin the first phase

## Rules
- Always confirm scope classification with the user before proceeding
- For Tier 4-5, recommend human-in-the-loop mode
- For Tier 1-2, suggest autonomous mode with auto permissions
