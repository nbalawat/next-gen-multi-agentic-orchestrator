---
name: tower
description: >
  Use this skill to display the RAPIDS Control Tower — a centralized governance
  dashboard across all workspaces and projects. Activates when the user asks
  for "dashboard", "control tower", "overview", "all projects status", or
  invokes /rapids-core:tower. Shows project health, cost, compliance, and alerts.
---

# RAPIDS Control Tower

Display the centralized governance dashboard across all workspaces and projects.

## Step 1: Generate Report

```bash
python3 -c "
from rapids_core.control_tower import generate_report, format_dashboard, alert_check
import json

report = generate_report()
print(format_dashboard(report))
"
```

## Step 2: Show Alerts

If there are alerts (red/yellow projects, pending gates, compliance issues),
highlight them prominently and use `AskUserQuestion` to let the user drill in:

```json
{
  "questions": [
    {
      "question": "There are alerts. Which would you like to investigate?",
      "header": "Alerts",
      "multiSelect": false,
      "options": [
        {
          "label": "<project_name> (RED)",
          "description": "<reason>"
        },
        {
          "label": "<project_name> (WARN)",
          "description": "<reason>"
        },
        {
          "label": "Export full report",
          "description": "Export as JSON or Markdown for external tools"
        }
      ]
    }
  ]
}
```

## Step 3: Drill Down (Optional)

If the user selects a project to investigate:
- `cd` into that project directory
- Run `/rapids-core:status` for detailed work item and activity view

## Step 4: Export (Optional)

If the user requests an export:

```bash
python3 -c "
from rapids_core.control_tower import generate_report, export_report
report = generate_report()
print(export_report(report, fmt='md'))  # or fmt='json'
"
```

## Rules
- Show the dashboard even if some projects have errors (graceful degradation)
- Always show alerts if any exist
- Use `AskUserQuestion` when there are actionable alerts
- Cost figures come from per-project cost.jsonl aggregation
