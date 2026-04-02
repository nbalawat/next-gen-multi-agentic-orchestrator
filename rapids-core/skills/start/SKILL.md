---
name: start
description: >
  Use this skill to begin a new RAPIDS project or resume an existing one.
  Activates when the user describes a project to build, asks to "start",
  or invokes /rapids-core:start. Auto-detects context to minimize prompts.
---

# RAPIDS Project Onboarding

**PRIORITY: Minimize friction.** Auto-detect everything possible. Only ask
questions when you genuinely cannot infer the answer.

---

## Step 0: Auto-Detect Context

Before asking ANY questions, check the current directory:

```bash
python3 -c "
import json
from pathlib import Path

cwd = '$(pwd)'
rapids_json = Path(cwd) / '.rapids' / 'rapids.json'
parent_rapids = any((Path(cwd).parent / d / '.rapids').is_dir() for d in Path(cwd).parent.iterdir() if d.is_dir()) if Path(cwd).parent.is_dir() else False

if rapids_json.exists():
    print('RESUME')  # Already in a RAPIDS project — just resume
elif Path(cwd).name == 'rapids-projects' or parent_rapids:
    print('WORKSPACE')  # In a workspace directory
else:
    print('NEW')  # Fresh start
"
```

### If RESUME (already in a RAPIDS project):

Skip ALL onboarding. Just show the phase banner and status:

```bash
python3 -c "
from rapids_core.config_loader import load_rapids_config, save_rapids_config
from rapids_core.work_item_manager import migrate_rapids_json, get_active_work_item, format_work_items_table, list_work_items
from rapids_core.ascii_art import phase_banner

config = load_rapids_config('.rapids')
config = migrate_rapids_json(config)
save_rapids_config('.rapids', config)
project_id = config.get('project', {}).get('id', 'unknown')
item = get_active_work_item(config)
items = list_work_items(config, active_only=False)
active_id = config.get('active_work_item')

if item:
    print(phase_banner(
        current_phase=item['current_phase'],
        activity=f'Active: {item[\"id\"]} — {item.get(\"title\", \"\")}',
        tier=item['tier'],
        project_name=project_id,
        phases_in_scope=item['phases'],
    ))
print(format_work_items_table(items, active_id))
"
```

Tell the user their project status and suggest `/rapids-core:go` to continue
or `/rapids-core:add` to add a bug fix or enhancement. **Done — no questions needed.**

### If WORKSPACE (in a workspace directory):

Show projects in this workspace and let user pick or create:

```bash
python3 -c "
import json
from pathlib import Path
from rapids_core.project_registry import get_workspace_projects, register_workspace
from rapids_core.onboarding import project_selection_question

cwd = '$(pwd)'
# Auto-register as workspace if not already
register_workspace(Path(cwd).name, cwd)
projects = get_workspace_projects(cwd)
print(json.dumps(project_selection_question(projects, cwd), indent=2))
"
```

Use `AskUserQuestion` with this payload. **ONE question only** — then proceed
to project creation or resume based on the answer.

### If NEW (fresh start):

Use `AskUserQuestion` to ask ONE combined question:

```json
{
  "questions": [
    {
      "question": "Where should this project live?",
      "header": "Location",
      "multiSelect": false,
      "options": [
        {
          "label": "Current directory (Recommended)",
          "description": "Initialize RAPIDS project right here"
        },
        {
          "label": "Create subdirectory",
          "description": "Create a new directory for this project (you'll type the name)"
        },
        {
          "label": "Different path",
          "description": "Specify an absolute path"
        }
      ]
    }
  ]
}
```

## Step 1: Classify and Initialize (if creating new project)

**If the user already described what to build** (e.g., "Build a REST API for todos"),
skip asking — use their description directly.

**If they just said "/start" with no description**, ask briefly:

```json
{
  "questions": [
    {
      "question": "What are you building?",
      "header": "Project",
      "multiSelect": false,
      "options": [
        {"label": "New application", "description": "Build from scratch"},
        {"label": "New feature", "description": "Add to existing codebase"},
        {"label": "Bug fix", "description": "Fix a specific issue"},
        {"label": "Refactor", "description": "Restructure existing code"}
      ]
    }
  ]
}
```

## Step 2: Scope Classification (auto — no question needed for Tier 1-3)

Run the scope classifier:
```bash
echo '<signals_json>' | ${CLAUDE_PLUGIN_ROOT}/scripts/scope-classifier.sh
```

**For Tier 1-3: auto-accept the classification.** Don't ask for confirmation —
just tell the user what tier was assigned and continue.

**For Tier 4-5 only:** Use `AskUserQuestion` to confirm scope since these are
major commitments.

## Step 3: Initialize

All in one step — no more questions:

1. Create `.rapids/` directory structure
2. Create `rapids.json` in **canonical format**:
   ```json
   {
     "project": {"id": "<project_name>"},
     "scope": {"tier": <tier>, "phases": <phases_list>},
     "current": {"phase": "<first_phase>"},
     "work_items": [{
       "id": "WI-001", "title": "<description>", "type": "<type>",
       "tier": <tier>, "phases": <phases_list>,
       "current_phase": "<first_phase>", "status": "active"
     }],
     "active_work_item": "WI-001",
     "plugins": []
   }
   ```
   **CRITICAL:** Use this exact nested format. Do NOT flatten it.
3. Copy phase templates for in-scope phases
4. Register project in central registry
5. Register workspace if applicable
6. Generate CLAUDE.md
7. Log to timeline

## Step 4: Show Result

Display the phase banner and tell the user:
- Project tier and phases
- That `/rapids-core:go` starts the first phase
- That `/rapids-core:add` can add work items later

**Total questions asked for a new project: 1-2 max (location + description if not provided).**
**Total questions for resuming: 0.**

## Rules
- **Auto-detect before asking** — if you can figure it out, don't ask
- **RESUME projects silently** — no questions, just show status
- **ONE question for workspace** — project selection, not workspace then project
- **Skip scope confirmation for Tier 1-3** — just tell the user
- **Use canonical rapids.json format** — nested `project`, `scope`, `current`, `work_items`
- **Use `AskUserQuestion` only when genuinely needed** — maximum 2 questions for new projects
