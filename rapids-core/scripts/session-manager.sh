#!/usr/bin/env bash
# Session Manager: track sessions, generate summaries, team handoffs
# Usage: session-manager.sh <command> [args]
# Commands: start, end, list, context, handoff, history
set -euo pipefail

COMMAND="${1:-}"
PROJECT_PATH="${2:-.}"

python3 -c "
import sys, json
from rapids_core.session_manager import (
    start_session, end_session, list_sessions,
    get_session_context, create_team_handoff,
    format_session_history,
)

command = '$COMMAND'
project_path = '$PROJECT_PATH'

if command == 'start':
    user = sys.argv[3] if len(sys.argv) > 3 else 'default'
    sid = start_session(user, project_path)
    print(json.dumps({'session_id': sid}))

elif command == 'end':
    sid = sys.argv[3] if len(sys.argv) > 3 else ''
    notes = sys.argv[4] if len(sys.argv) > 4 else ''
    result = end_session(sid, project_path, handoff_notes=notes)
    print(json.dumps(result, indent=2))

elif command == 'list':
    user = sys.argv[3] if len(sys.argv) > 3 else None
    sessions = list_sessions(project_path, user=user)
    print(format_session_history(sessions))

elif command == 'context':
    sid = sys.argv[3] if len(sys.argv) > 3 else ''
    ctx = get_session_context(sid, project_path)
    if ctx:
        print(json.dumps(ctx, indent=2))
    else:
        print(f'Session {sid} not found', file=sys.stderr)
        sys.exit(1)

elif command == 'handoff':
    sid = sys.argv[3] if len(sys.argv) > 3 else ''
    to_user = sys.argv[4] if len(sys.argv) > 4 else ''
    notes = sys.argv[5] if len(sys.argv) > 5 else ''
    result = create_team_handoff(sid, to_user, project_path, notes=notes)
    print(json.dumps(result, indent=2))

else:
    print('Usage: session-manager.sh <start|end|list|context|handoff> <project_path> [args]', file=sys.stderr)
    sys.exit(1)
" "$@"
