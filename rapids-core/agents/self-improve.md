---
name: self-improve
description: >
  Self-improve prompt for agent expertise. After completing work, the agent
  reviews what happened, identifies learnings, and updates its own expertise.yaml
  mental model. This is NOT documentation — it's working memory validated against code.
model: sonnet
effort: low
maxTurns: 20
tools: Read, Write, Edit, Bash, Grep, Glob
---

# Self-Improve: Update Your Expertise

You have just completed work. Now update your expertise file to capture what
you learned. Your expertise file is your **mental model** — working memory that
helps you work faster and better next time.

## Principles

1. **Code is the source of truth** — your expertise file is working memory, not documentation
2. **Focus on high-value knowledge** — patterns, pitfalls, domain-specific insights
3. **Keep it under 1000 lines** — trim least important if over limit
4. **Be concrete** — include file paths, function names, specific patterns
5. **Track confidence** — lessons reinforced across sessions get higher confidence

## Workflow

### Step 1: Load Current Expertise

```bash
python3 -c "
from rapids_core.knowledge_fabric import load_agent_expertise, format_expertise_summary
expertise = load_agent_expertise('<YOUR_AGENT_NAME>')
if expertise:
    print(format_expertise_summary('<YOUR_AGENT_NAME>'))
else:
    print('No existing expertise — starting fresh')
"
```

### Step 2: Review What Happened This Session

Check the feature progress files for outcomes:
```bash
python3 -c "
import json
from pathlib import Path
impl_dir = Path('.rapids/phases/implement')
for pf in sorted(impl_dir.glob('feature-progress-*.json')):
    progress = json.loads(pf.read_text())
    fid = progress.get('feature_id', '?')
    status = progress.get('status', '?')
    verdict = progress.get('evaluator_verdict', '?')
    retries = progress.get('retry_count', 0)
    print(f'{fid}: {status} (verdict: {verdict}, retries: {retries})')
"
```

### Step 3: Identify Learnings

For each feature you worked on, ask yourself:
- What patterns worked well? (→ add as lesson)
- What did I get wrong on the first try? (→ add as pitfall)
- What domain knowledge did I use or discover? (→ add to domain_knowledge)
- Did the evaluator catch something I missed? (→ add as pitfall)

### Step 4: Update Expertise

```bash
python3 -c "
from rapids_core.knowledge_fabric import add_lesson, add_pitfall, record_session_outcome

# Record session stats
record_session_outcome(
    '<YOUR_AGENT_NAME>',
    features_passed=<N>,
    features_failed=<N>,
    total_retries=<N>,
    session_id='<SESSION_ID>',
)

# Add lessons learned
add_lesson('<YOUR_AGENT_NAME>', '<LESSON_TEXT>', source='<SESSION_ID>', confidence=0.6)

# Add pitfalls discovered
add_pitfall('<YOUR_AGENT_NAME>', '<PITFALL>', '<MITIGATION>')
"
```

### Step 5: Validate

```bash
python3 -c "
import yaml
from rapids_core.knowledge_fabric import load_agent_expertise
expertise = load_agent_expertise('<YOUR_AGENT_NAME>')
content = yaml.dump(expertise, default_flow_style=False)
lines = content.split('\n')
print(f'Expertise file: {len(lines)} lines (max 1000)')
if len(lines) > 1000:
    print('WARNING: Over limit — trimming needed')
"
```

## Rules

- **Only update based on real outcomes** — don't speculate
- **High confidence requires multiple reinforcements** — start lessons at 0.5-0.6
- **Pitfalls need mitigations** — don't just log problems, log solutions
- **Trim ruthlessly** — if over 1000 lines, remove lowest-confidence entries
- **Keep domain_knowledge structured** — use categories and subcategories
