#!/usr/bin/env bash
# Control Tower: centralized governance dashboard
# Usage: control-tower.sh <command>
# Commands: dashboard, report-json, report-md, alerts, health, compliance
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

COMMAND="${1:-dashboard}"

python3 -c "
import sys, json
from rapids_core.control_tower import (
    generate_report, format_dashboard, export_report,
    alert_check, project_health, compliance_check,
)

command = '$COMMAND'

if command == 'dashboard':
    report = generate_report()
    print(format_dashboard(report))

elif command == 'report-json':
    report = generate_report()
    print(export_report(report, fmt='json'))

elif command == 'report-md':
    report = generate_report()
    print(export_report(report, fmt='md'))

elif command == 'alerts':
    report = generate_report()
    alerts = alert_check(report)
    if alerts:
        for a in alerts:
            print(a)
    else:
        print('No alerts.')

elif command == 'health':
    path = sys.argv[2] if len(sys.argv) > 2 else '.'
    result = project_health(path)
    print(json.dumps(result, indent=2))

elif command == 'compliance':
    path = sys.argv[2] if len(sys.argv) > 2 else '.'
    result = compliance_check(path)
    print(json.dumps(result, indent=2))

else:
    print(f'Unknown command: {command}', file=sys.stderr)
    print('Commands: dashboard, report-json, report-md, alerts, health, compliance', file=sys.stderr)
    sys.exit(1)
" "$@"
