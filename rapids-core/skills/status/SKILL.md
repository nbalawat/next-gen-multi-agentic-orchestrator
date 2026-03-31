---
name: status
description: >
  Use this skill to check RAPIDS project status. Activates when the user asks
  "what's the status", "how far along", "show progress", or invokes
  /rapids-core:status. Shows current phase, feature progress, cost summary,
  and any blocked items. Use /btw for quick status checks during active work.
---

# RAPIDS Project Status

Read the current project state and present a visual status report with ASCII art.

## Step 1: Display Phase Banner

First, read `.rapids/rapids.json` to get current state, then display the phase banner:
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
    activity='Status check',
    tier=tier,
    project_name=project_id,
    phases_in_scope=phases,
))
"
```

## Step 2: Gather Data

1. **rapids.json** — Current phase, tier, active plugins
2. **feature-progress.json files** — Per-feature completion status
3. **cost.jsonl** — Cost tracking (run `${CLAUDE_PLUGIN_ROOT}/scripts/cost-tracker.sh`)
4. **timeline.jsonl** — Event history

## Step 3: Status Report Format

Present status using the phase banner displayed above, followed by this detail:

```
Features:
  ✓ F001: [name] — complete
  → F002: [name] — in progress (3/5 criteria done)
  ○ F003: [name] — pending (blocked by F001)
  ✗ F004: [name] — failed (evaluator feedback pending)

Wave Progress: Wave 2 of 3
  Wave 1: ✓ complete (merged)
  Wave 2: → in progress (2/3 features done)
  Wave 3: ○ pending

Cost: $X.XX total
  Analysis: $X.XX | Plan: $X.XX | Implement: $X.XX
```

## Step 4: Show All Managed Projects

At the end of the status output, show the full list of managed projects:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/project-registry.sh list
```

## Tips
- Use `/btw what's the status?` during active work to avoid context disruption
- For mobile monitoring, enable Remote Control: `claude remote-control`
