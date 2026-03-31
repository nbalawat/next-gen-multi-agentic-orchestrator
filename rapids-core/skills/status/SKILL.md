---
name: status
description: >
  Use this skill to check RAPIDS project status. Activates when the user asks
  "what's the status", "how far along", "show progress", or invokes
  /rapids-core:status. Shows current phase, feature progress, cost summary,
  and any blocked items. Use /btw for quick status checks during active work.
---

# RAPIDS Project Status

Read the current project state and present a concise status report.

## Data Sources

1. **rapids.json** — Current phase, tier, active plugins
2. **feature-progress.json files** — Per-feature completion status
3. **cost.jsonl** — Cost tracking (run `${CLAUDE_PLUGIN_ROOT}/scripts/cost-tracker.sh`)
4. **timeline.jsonl** — Event history

## Status Report Format

```
RAPIDS Status: [Project ID]
═══════════════════════════════
Phase: [current phase] | Tier: [tier]
Plugins: [active plugins]

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

## Tips
- Use `/btw what's the status?` during active work to avoid context disruption
- For mobile monitoring, enable Remote Control: `claude remote-control`
