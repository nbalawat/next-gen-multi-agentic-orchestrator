---
name: status
description: >
  Use this skill to check RAPIDS project status. Activates when the user asks
  "what's the status", "how far along", "show progress", or invokes
  /rapids-core:status. Shows all work items with their individual phases,
  feature progress, cost summary, and blocked items. Use /btw for quick checks.
---

# RAPIDS Project Status

Read the current project state and present a visual status report with ASCII art.

## Step 1: Load Work Items & Display Active Phase Banner

```bash
python3 -c "
import json
from pathlib import Path
from rapids_core.ascii_art import phase_banner
from rapids_core.work_item_manager import migrate_rapids_json, get_active_work_item, list_work_items, format_work_items_table

config = json.loads(Path('.rapids/rapids.json').read_text())
config = migrate_rapids_json(config)
Path('.rapids/rapids.json').write_text(json.dumps(config, indent=2))

project_id = config.get('project', {}).get('id', 'unknown')
active = get_active_work_item(config)

if active:
    print(phase_banner(
        current_phase=active['current_phase'],
        activity=f'Active: {active[\"id\"]} — {active.get(\"title\", \"\")}',
        tier=active['tier'],
        project_name=project_id,
        phases_in_scope=active['phases'],
    ))
"
```

## Step 2: Show All Work Items

Display the full work items table showing all items with their independent phases:

```bash
python3 -c "
import json
from pathlib import Path
from rapids_core.work_item_manager import migrate_rapids_json, list_work_items, format_work_items_table

config = json.loads(Path('.rapids/rapids.json').read_text())
config = migrate_rapids_json(config)
items = list_work_items(config, active_only=False)
active_id = config.get('active_work_item')
print(format_work_items_table(items, active_id))
"
```

This shows each work item with:
- `▶` marker on the active item
- `●` for active, `✓` for complete, `○` for pending
- Each item's own tier, phase, and status

## Step 3: Gather Data

1. **rapids.json** — Work items, active item, plugins
2. **feature-progress.json files** — Per-feature completion status
3. **cost.jsonl** — Cost tracking (run `${CLAUDE_PLUGIN_ROOT}/scripts/cost-tracker.sh`)
4. **timeline.jsonl** — Event history

## Step 4: Status Report Format

Present status per work item:

```
Work Items:
  ▶ WI-001: Build payment API          T4  deploy       ● active
    WI-002: Fix login crash             T1  implement    ● active
    WI-003: Add caching layer           T2  plan         ● active
  ──────────────────────────────────────────────────────────────

Active Work Item: WI-001 — Build payment API
  Phase: deploy (4/5 phases complete)

  Features:
    ✓ F001: Payment endpoints — complete
    ✓ F002: Database models — complete
    → F003: Deployment config — in progress (2/3 criteria done)

  Wave Progress: Wave 3 of 3
    Wave 1: ✓ complete (merged)
    Wave 2: ✓ complete (merged)
    Wave 3: → in progress

Cost: $X.XX total
  Analysis: $X.XX | Plan: $X.XX | Implement: $X.XX
```

## Step 5: Show Managed Projects

At the end of the status output, show the full list of managed projects:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/project-registry.sh list
```

## Tips
- Use `/btw what's the status?` during active work to avoid context disruption
- Use `/rapids-core:add` to add a new bug fix or enhancement to the current project
- For mobile monitoring, enable Remote Control: `claude remote-control`
