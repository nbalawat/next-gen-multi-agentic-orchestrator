---
name: export
description: >
  Use this skill to export RAPIDS project artifacts as a client-facing package.
  Activates when the user says "export", "create deliverable", "package for client",
  or invokes /rapids-core:export. Assembles architecture docs, ADRs, feature specs,
  test reports, and cost summary into a clean export directory.
---

# RAPIDS Export Package

Assemble project artifacts into a client-facing deliverable package.

## Export Structure

```
export/
├── README.md                    # Project overview and summary
├── architecture/
│   ├── solution-design.md       # From analysis phase
│   └── adrs/                    # Architecture Decision Records
├── features/
│   ├── feature-specs/           # Feature specifications (XML → rendered)
│   └── dependency-graph.md      # Visual dependency graph
├── implementation/
│   ├── test-report.md           # Test results summary
│   └── feature-progress.md      # Final feature status
├── cost-summary.md              # Cost breakdown by phase
└── timeline.md                  # Key milestones and decisions
```

## Steps

1. **Gather artifacts** from `.rapids/phases/`
2. **Generate cost summary** using `${CLAUDE_PLUGIN_ROOT}/scripts/cost-tracker.sh`
3. **Render feature specs** from XML to readable markdown
4. **Create README** with project overview, tier, phases completed, key decisions
5. **Copy to export directory**

## Rules
- Exclude internal RAPIDS state (rapids.json, accumulated.json)
- Exclude raw audit logs (cost.jsonl, timeline.jsonl) — summarize instead
- Make all documents self-contained and readable without RAPIDS context
- Include cost transparency — clients should see what was spent where
