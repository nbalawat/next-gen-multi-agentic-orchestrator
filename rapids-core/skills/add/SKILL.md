---
name: add
description: >
  Use this skill to add a new work item (bug fix, enhancement, feature, or refactor)
  to an existing RAPIDS project. Activates when the user says "add a bug fix",
  "new enhancement", "I need to fix...", "add a feature", or invokes /rapids-core:add.
  Each work item gets its own tier and independent phase progression, so you can fix
  bugs while the main feature is in Deploy.
---

# RAPIDS — Add Work Item

You are adding a new work item to an existing RAPIDS project. Work items allow
concurrent bug fixes, enhancements, and features within the same project, each
with their own tier and phase lifecycle.

**IMPORTANT:** Use the `AskUserQuestion` tool at every decision point.

---

## Step 1: Verify Project Exists

Check that `.rapids/rapids.json` exists in the current directory. If not, tell
the user to run `/rapids-core:start` first.

## Step 2: Show Current Work Items

Display the current project state with all work items:

```bash
python3 -c "
import json
from pathlib import Path
from rapids_core.work_item_manager import migrate_rapids_json, list_work_items, format_work_items_table

config = json.loads(Path('.rapids/rapids.json').read_text())
config = migrate_rapids_json(config)
Path('.rapids/rapids.json').write_text(json.dumps(config, indent=2))

items = list_work_items(config, active_only=False)
active_id = config.get('active_work_item')
print(format_work_items_table(items, active_id))
"
```

## Step 3: Ask Work Item Type (AskUserQuestion)

```json
{
  "questions": [
    {
      "question": "What type of work item are you adding?",
      "header": "Type",
      "multiSelect": false,
      "options": [
        {
          "label": "Bug fix",
          "description": "Fix a specific bug or issue. Typically Tier 1 (implement only)."
        },
        {
          "label": "Enhancement",
          "description": "Improve existing functionality. Typically Tier 2 (plan + implement)."
        },
        {
          "label": "Feature",
          "description": "Add new functionality. Tier 3-5 depending on scope."
        },
        {
          "label": "Refactor",
          "description": "Restructure code without changing behavior. Typically Tier 1-2."
        }
      ]
    }
  ]
}
```

Map the response to a type: "bug", "enhancement", "feature", "refactor".

## Step 4: Get Description

Ask the user to describe the work item. If they already provided a description
(e.g., "add a bug fix for the login crash"), use that.

## Step 5: Classify Scope

Run the scope classifier based on the description:
```bash
echo '<signals_json>' | ${CLAUDE_PLUGIN_ROOT}/scripts/scope-classifier.sh
```

**Shortcut tiers by type:**
- Bug fixes default to Tier 1 unless the user's description suggests more complexity
- Enhancements default to Tier 2
- Refactors default to Tier 1-2
- Features get full classification

## Step 6: Confirm Scope (AskUserQuestion)

Use `AskUserQuestion` to confirm the tier (same as start skill Step 5).

## Step 7: Create Work Item

```bash
python3 -c "
import json
from pathlib import Path
from rapids_core.work_item_manager import create_work_item

config = json.loads(Path('.rapids/rapids.json').read_text())
item = create_work_item(
    config,
    title='<user_description>',
    item_type='<type>',
    tier=<tier>,
)
Path('.rapids/rapids.json').write_text(json.dumps(config, indent=2))
print(json.dumps(item, indent=2))
"
```

## Step 8: Display Phase Banner

Show the phase banner for the new work item:

```bash
python3 -c "
from rapids_core.ascii_art import phase_banner
print(phase_banner(
    current_phase='<first_phase>',
    activity='New work item: <title>',
    tier=<tier>,
    project_name='<project_id>',
    phases_in_scope=<phases>,
))
"
```

## Step 9: Regenerate CLAUDE.md

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/claude-md-generator.sh .
```

## Step 10: Summary

Tell the user:
- Work item ID and type
- Tier and phases
- That it's now the active work item
- Run `/rapids-core:go` to begin working on it
- Run `/rapids-core:status` to see all work items

## Rules
- **MUST use `AskUserQuestion` tool** for type selection and scope confirmation
- Always show existing work items before creating a new one
- New work items automatically become the active item
- Bug fixes default to Tier 1 (fast path: straight to implement)
- Always regenerate CLAUDE.md after creating a work item
