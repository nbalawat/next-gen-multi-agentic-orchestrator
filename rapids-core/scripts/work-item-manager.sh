#!/usr/bin/env bash
# Work item manager: manages work items within a RAPIDS project
# Usage: work-item-manager.sh <command> [args]
# Commands: list, create, switch, advance, complete, migrate
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

COMMAND="${1:-}"

if [ -z "$COMMAND" ]; then
    echo "Usage: work-item-manager.sh <command>" >&2
    echo "Commands: list, create, switch, advance, complete, migrate" >&2
    exit 1
fi

RAPIDS_JSON="${2:-.rapids/rapids.json}"

python3 -c "
import sys, json
from pathlib import Path
from rapids_core.work_item_manager import (
    migrate_rapids_json, create_work_item, list_work_items,
    switch_work_item, advance_work_item_phase, complete_work_item,
    format_work_items_table,
)

command = '$COMMAND'
rapids_json_path = Path('$RAPIDS_JSON')
config = json.loads(rapids_json_path.read_text())

if command == 'migrate':
    config = migrate_rapids_json(config)
    rapids_json_path.write_text(json.dumps(config, indent=2))
    print('Migrated successfully')

elif command == 'list':
    config = migrate_rapids_json(config)
    items = list_work_items(config, active_only='--all' not in sys.argv)
    active_id = config.get('active_work_item')
    print(format_work_items_table(items, active_id))

elif command == 'create':
    data = json.loads(sys.stdin.read())
    item = create_work_item(config, data['title'], data['type'], tier=data.get('tier'))
    rapids_json_path.write_text(json.dumps(config, indent=2))
    print(json.dumps(item, indent=2))

elif command == 'switch':
    wi_id = sys.argv[3] if len(sys.argv) > 3 else ''
    if not wi_id:
        print('Usage: work-item-manager.sh switch <rapids.json> <work_item_id>', file=sys.stderr)
        sys.exit(1)
    switch_work_item(config, wi_id)
    rapids_json_path.write_text(json.dumps(config, indent=2))
    print(json.dumps({'active_work_item': wi_id}))

elif command == 'advance':
    wi_id = sys.argv[3] if len(sys.argv) > 3 else config.get('active_work_item', '')
    result = advance_work_item_phase(config, wi_id)
    rapids_json_path.write_text(json.dumps(config, indent=2))
    if result:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps({'error': 'Already at last phase'}))

elif command == 'complete':
    wi_id = sys.argv[3] if len(sys.argv) > 3 else config.get('active_work_item', '')
    result = complete_work_item(config, wi_id)
    rapids_json_path.write_text(json.dumps(config, indent=2))
    print(json.dumps(result, indent=2))

else:
    print(f'Unknown command: {command}', file=sys.stderr)
    sys.exit(1)
" "$@"
