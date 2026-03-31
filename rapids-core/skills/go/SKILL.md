---
name: go
description: >
  Use this skill to advance the RAPIDS project to the next phase or continue
  work in the current phase. Activates when the user says "go", "continue",
  "proceed", "next phase", or invokes /rapids-core:go. Handles phase gate
  verification, phase transitions, and wave execution.
---

# RAPIDS Phase Advancement

## Step 1: Check Current State
Read `.rapids/rapids.json` to determine:
- Current phase
- Next phase in the sequence
- Whether phase gate conditions are met

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

## Step 3: Phase Transition
Update `rapids.json` with the new phase, regenerate `CLAUDE.md`:
```bash
${CLAUDE_PLUGIN_ROOT}/scripts/claude-md-generator.sh .
```

## Step 4: Phase-Specific Execution

### If entering IMPLEMENT phase:
1. Compute implementation waves:
   ```bash
   cat .rapids/phases/plan/dependency-graph.json | ${CLAUDE_PLUGIN_ROOT}/scripts/wave-computer.sh
   ```

2. **Choose execution method per wave:**
   - Independent features, single-plugin, Tier 2-3 → Use `/batch`
   - Coordinated features, multi-plugin, Tier 4-5 → Use Agent Teams

3. **For each feature in the wave:**
   - Generator implements incrementally (one criterion at a time)
   - `/simplify` runs on changed files (3 parallel review agents)
   - Evaluator verifies independently
   - If pass → merge; if fail → feedback to Generator (max 3 retries)

4. **Permission model:**
   - Autonomous mode → enable auto mode (`--enable-auto-mode`)
   - Human-in-the-loop → standard approval (Tier 4-5, client envs)
   - Hybrid (recommended) → auto mode within waves, manual at wave boundaries

5. **Monitoring (autonomous mode):**
   - Set up progress polling: `/loop 5m "check feature progress"`
   - Suggest Remote Control for mobile monitoring
   - Use `/btw` for side questions without disrupting work

### If entering DEPLOY phase:
- Prefer event-driven execution via Channels over polling
- CI/CD events push "build complete" → RAPIDS reacts
- Run smoke tests after deployment

## Rules
- Always show the user what's about to happen before starting a wave
- In hybrid mode, pause at wave boundaries for human approval
- Log all phase transitions to timeline.jsonl
