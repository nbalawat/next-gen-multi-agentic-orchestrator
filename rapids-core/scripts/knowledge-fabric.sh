#!/usr/bin/env bash
# Knowledge Fabric: agent expertise management
# Usage: knowledge-fabric.sh <command> <agent_name> [args]
# Commands: init, load, inject, record, lesson, pitfall, summary, trim
set -euo pipefail

COMMAND="${1:-}"
AGENT="${2:-}"

if [ -z "$COMMAND" ] || [ -z "$AGENT" ]; then
    echo "Usage: knowledge-fabric.sh <command> <agent_name> [args]" >&2
    echo "Commands: init, load, inject, record, lesson, pitfall, summary, trim" >&2
    exit 1
fi

python3 -c "
import sys, json
from rapids_core.knowledge_fabric import (
    initialize_agent_expertise, load_agent_expertise, save_agent_expertise,
    get_prompt_injections, record_session_outcome, add_lesson, add_pitfall,
    format_expertise_summary, trim_expertise,
)

command = '$COMMAND'
agent = '$AGENT'

if command == 'init':
    defn = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    expertise = initialize_agent_expertise(agent, agent_definition=defn)
    print(json.dumps(expertise, indent=2, default=str))

elif command == 'load':
    expertise = load_agent_expertise(agent)
    if expertise:
        print(json.dumps(expertise, indent=2, default=str))
    else:
        print(f'No expertise for {agent}', file=sys.stderr)
        sys.exit(1)

elif command == 'inject':
    print(get_prompt_injections(agent))

elif command == 'record':
    data = json.loads(sys.stdin.read())
    expertise = record_session_outcome(
        agent,
        features_passed=data.get('features_passed', 0),
        features_failed=data.get('features_failed', 0),
        total_retries=data.get('total_retries', 0),
        session_id=data.get('session_id', ''),
    )
    print(json.dumps(expertise, indent=2, default=str))

elif command == 'lesson':
    data = json.loads(sys.stdin.read())
    expertise = add_lesson(agent, data['lesson'], source=data.get('source', ''), confidence=data.get('confidence', 0.5))
    print('Lesson added/reinforced')

elif command == 'pitfall':
    data = json.loads(sys.stdin.read())
    expertise = add_pitfall(agent, data['pitfall'], data['mitigation'])
    print('Pitfall added/updated')

elif command == 'summary':
    print(format_expertise_summary(agent))

elif command == 'trim':
    expertise = load_agent_expertise(agent)
    if expertise:
        trimmed = trim_expertise(expertise)
        save_agent_expertise(agent, trimmed)
        print('Trimmed successfully')
    else:
        print(f'No expertise for {agent}', file=sys.stderr)

else:
    print(f'Unknown command: {command}', file=sys.stderr)
    sys.exit(1)
" "$@"
