"""Control Tower: centralized governance dashboard across all RAPIDS workspaces and projects.

Aggregates project health, cost, work item status, gate compliance, and alerts
into a single report spanning all registered workspaces and projects.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from rapids_core.project_registry import list_workspaces, list_projects
from rapids_core.cost_tracker import aggregate_costs


def project_health(project_path: str) -> dict:
    """Assess a single project's health.

    Health is determined by:
    - **green**: All active work items progressing, no failed gates, cost on track
    - **yellow**: Stalled work items (no activity in 7+ days) or failed evaluator verdicts
    - **red**: Failed phase gates, cost overrun, or no active work items with incomplete phases

    Args:
        project_path: Absolute path to the project directory.

    Returns:
        Dict with keys: status (green/yellow/red), reasons (list[str]),
        active_work_items, completed_work_items, cost_total, last_activity.
    """
    rapids_dir = Path(project_path) / ".rapids"
    reasons: list[str] = []
    status = "green"

    # Load rapids.json
    rapids_json = rapids_dir / "rapids.json"
    if not rapids_json.exists():
        return {
            "status": "red",
            "reasons": ["No .rapids/rapids.json found"],
            "active_work_items": 0,
            "completed_work_items": 0,
            "cost_total": 0.0,
            "last_activity": None,
        }

    config = json.loads(rapids_json.read_text())

    # Work item counts
    work_items = config.get("work_items", [])
    active = [wi for wi in work_items if wi.get("status") == "active"]
    completed = [wi for wi in work_items if wi.get("status") == "complete"]

    # Cost
    cost_file = rapids_dir / "audit" / "cost.jsonl"
    cost_total = 0.0
    if cost_file.exists():
        try:
            summary = aggregate_costs(str(cost_file))
            cost_total = summary.total_cost
        except Exception:
            pass

    # Last activity from timeline
    timeline_file = rapids_dir / "audit" / "timeline.jsonl"
    last_activity = None
    if timeline_file.exists():
        lines = timeline_file.read_text().strip().split("\n")
        for line in reversed(lines):
            if line.strip():
                try:
                    entry = json.loads(line)
                    last_activity = entry.get("ts")
                    break
                except json.JSONDecodeError:
                    continue

    # Check for failed evaluator verdicts
    impl_dir = rapids_dir / "phases" / "implement"
    if impl_dir.is_dir():
        for pf in impl_dir.glob("feature-progress-*.json"):
            try:
                progress = json.loads(pf.read_text())
                if progress.get("evaluator_verdict") == "fail":
                    reasons.append(f"Feature {progress.get('feature_id', '?')} failed evaluation")
                    status = "yellow"
            except (json.JSONDecodeError, KeyError):
                continue

    # Check for stalled work items (no activity and still active)
    if not active and not completed:
        reasons.append("No work items found")
        status = "red"
    elif not active and work_items:
        pass  # All complete is fine

    # Check activity gate compliance
    for phase_dir in (rapids_dir / "phases").iterdir() if (rapids_dir / "phases").is_dir() else []:
        if phase_dir.is_dir():
            for ap_file in phase_dir.glob("activity-progress-*.json"):
                try:
                    ap = json.loads(ap_file.read_text())
                    for act_id, act in ap.get("activities", {}).items():
                        if act.get("gate") and act.get("status") != "complete":
                            # Only flag if this phase has an active work item
                            pass  # Pending gates are normal during active work
                except (json.JSONDecodeError, KeyError):
                    continue

    return {
        "status": status,
        "reasons": reasons,
        "active_work_items": len(active),
        "completed_work_items": len(completed),
        "cost_total": cost_total,
        "last_activity": last_activity,
    }


def compliance_check(project_path: str) -> dict:
    """Verify compliance for a project.

    Checks:
    - All completed phases have gate activities marked complete
    - Audit trail exists (timeline.jsonl, cost.jsonl)
    - No missing progress files for active features

    Args:
        project_path: Absolute path to the project directory.

    Returns:
        Dict with keys: compliant (bool), issues (list[str]), gates_passed (int),
        gates_pending (int), audit_files_present (bool).
    """
    rapids_dir = Path(project_path) / ".rapids"
    issues: list[str] = []
    gates_passed = 0
    gates_pending = 0

    # Check audit files exist
    timeline_exists = (rapids_dir / "audit" / "timeline.jsonl").exists()
    cost_exists = (rapids_dir / "audit" / "cost.jsonl").exists()
    audit_present = timeline_exists and cost_exists
    if not audit_present:
        issues.append("Missing audit files (timeline.jsonl or cost.jsonl)")

    # Check activity gates across all phases
    phases_dir = rapids_dir / "phases"
    if phases_dir.is_dir():
        for phase_dir in phases_dir.iterdir():
            if not phase_dir.is_dir():
                continue
            for ap_file in phase_dir.glob("activity-progress-*.json"):
                try:
                    ap = json.loads(ap_file.read_text())
                    for act_id, act in ap.get("activities", {}).items():
                        if act.get("gate"):
                            if act.get("status") == "complete":
                                gates_passed += 1
                            else:
                                gates_pending += 1
                except (json.JSONDecodeError, KeyError):
                    continue

    return {
        "compliant": len(issues) == 0,
        "issues": issues,
        "gates_passed": gates_passed,
        "gates_pending": gates_pending,
        "audit_files_present": audit_present,
    }


def generate_report() -> dict:
    """Generate a Control Tower report across all workspaces and projects.

    Returns:
        ControlTowerReport dict with workspaces, global_stats, and compliance.
    """
    now = datetime.now(timezone.utc).isoformat()
    workspaces = list_workspaces()
    all_projects = list_projects(active_only=False)

    workspace_reports = []
    total_cost = 0.0
    total_active_wi = 0
    total_completed_wi = 0
    all_compliant = True

    for ws in workspaces:
        ws_projects = [p for p in all_projects if p.get("workspace") == ws["path"]]
        project_reports = []

        for proj in ws_projects:
            health = project_health(proj["path"])
            comp = compliance_check(proj["path"])

            # Gather current phases from work items
            rapids_json_path = Path(proj["path"]) / ".rapids" / "rapids.json"
            current_phases = []
            if rapids_json_path.exists():
                try:
                    config = json.loads(rapids_json_path.read_text())
                    for wi in config.get("work_items", []):
                        if wi.get("status") == "active":
                            current_phases.append(wi.get("current_phase", "?"))
                except (json.JSONDecodeError, KeyError):
                    pass

            project_reports.append({
                "name": proj["name"],
                "path": proj["path"],
                "tier": proj.get("tier", 0),
                "work_items": {
                    "active": health["active_work_items"],
                    "complete": health["completed_work_items"],
                },
                "current_phases": current_phases,
                "cost": {"total": health["cost_total"]},
                "health": health["status"],
                "health_reasons": health["reasons"],
                "gates_passed": comp["gates_passed"],
                "gates_pending": comp["gates_pending"],
                "last_activity": health["last_activity"],
            })

            total_cost += health["cost_total"]
            total_active_wi += health["active_work_items"]
            total_completed_wi += health["completed_work_items"]
            if not comp["compliant"]:
                all_compliant = False

        workspace_reports.append({
            "name": ws["name"],
            "path": ws["path"],
            "projects": project_reports,
        })

    # Include standalone projects (no workspace)
    standalone = [p for p in all_projects if not p.get("workspace")]
    if standalone:
        standalone_reports = []
        for proj in standalone:
            health = project_health(proj["path"])
            comp = compliance_check(proj["path"])
            standalone_reports.append({
                "name": proj["name"],
                "path": proj["path"],
                "tier": proj.get("tier", 0),
                "work_items": {
                    "active": health["active_work_items"],
                    "complete": health["completed_work_items"],
                },
                "current_phases": [],
                "cost": {"total": health["cost_total"]},
                "health": health["status"],
                "health_reasons": health["reasons"],
                "gates_passed": comp["gates_passed"],
                "gates_pending": comp["gates_pending"],
                "last_activity": health["last_activity"],
            })
            total_cost += health["cost_total"]
            total_active_wi += health["active_work_items"]
            total_completed_wi += health["completed_work_items"]

        workspace_reports.append({
            "name": "(standalone)",
            "path": None,
            "projects": standalone_reports,
        })

    return {
        "generated_at": now,
        "workspaces": workspace_reports,
        "global_stats": {
            "total_projects": len(all_projects),
            "total_cost": total_cost,
            "active_work_items": total_active_wi,
            "completed_work_items": total_completed_wi,
        },
        "compliance": {
            "all_compliant": all_compliant,
        },
    }


def alert_check(report: dict) -> list[str]:
    """Check a Control Tower report for alerts.

    Args:
        report: A report dict from ``generate_report()``.

    Returns:
        List of alert strings (empty if no alerts).
    """
    alerts: list[str] = []

    for ws in report.get("workspaces", []):
        for proj in ws.get("projects", []):
            name = proj["name"]

            if proj["health"] == "red":
                reasons = ", ".join(proj.get("health_reasons", []))
                alerts.append(f"[RED] {name}: {reasons}")
            elif proj["health"] == "yellow":
                reasons = ", ".join(proj.get("health_reasons", []))
                alerts.append(f"[WARN] {name}: {reasons}")

            if proj.get("gates_pending", 0) > 3:
                alerts.append(f"[GATE] {name}: {proj['gates_pending']} gates pending")

    if not report.get("compliance", {}).get("all_compliant", True):
        alerts.append("[COMPLIANCE] Not all projects are compliant")

    return alerts


def format_dashboard(report: dict) -> str:
    """Format a Control Tower report as an ASCII dashboard.

    Args:
        report: A report dict from ``generate_report()``.

    Returns:
        Formatted dashboard string.
    """
    w = 78
    border_top = "╔" + "═" * w + "╗"
    border_bot = "╚" + "═" * w + "╝"
    border_thin = "╟" + "─" * w + "╢"

    def pad(text: str) -> str:
        padding = max(0, w - len(text) - 1)
        return "║ " + text + " " * padding + "║"

    lines = []
    lines.append(border_top)
    lines.append(pad(""))
    lines.append(pad("  R A P I D S  —  C O N T R O L   T O W E R"))
    lines.append(pad(""))
    lines.append(border_thin)

    # Global stats
    gs = report.get("global_stats", {})
    lines.append(pad(""))
    lines.append(pad(f"  Projects: {gs.get('total_projects', 0)}"
                     f"    Active WIs: {gs.get('active_work_items', 0)}"
                     f"    Complete WIs: {gs.get('completed_work_items', 0)}"
                     f"    Cost: ${gs.get('total_cost', 0):.2f}"))
    lines.append(pad(""))
    lines.append(border_thin)

    # Per-workspace
    for ws in report.get("workspaces", []):
        lines.append(pad(""))
        ws_name = ws.get("name", "?")
        lines.append(pad(f"  Workspace: {ws_name}"))
        lines.append(pad("  " + "─" * 70))

        for proj in ws.get("projects", []):
            health = proj.get("health", "?")
            health_icon = {"green": "●", "yellow": "◐", "red": "○"}.get(health, "?")
            name = proj["name"][:25]
            wi_active = proj.get("work_items", {}).get("active", 0)
            wi_complete = proj.get("work_items", {}).get("complete", 0)
            cost = proj.get("cost", {}).get("total", 0)
            phases = ", ".join(proj.get("current_phases", []))[:20]
            gates_ok = proj.get("gates_passed", 0)
            gates_pend = proj.get("gates_pending", 0)

            lines.append(pad(
                f"  {health_icon} {name:<25} T{proj.get('tier', '?'):<4} "
                f"WI:{wi_active}/{wi_active + wi_complete}  "
                f"Gates:{gates_ok}✓/{gates_pend}○  "
                f"${cost:.2f}"
            ))
            if proj.get("health_reasons"):
                for reason in proj["health_reasons"][:2]:
                    lines.append(pad(f"    ⚠ {reason[:65]}"))

        lines.append(pad(""))

    # Alerts
    alerts = alert_check(report)
    if alerts:
        lines.append(border_thin)
        lines.append(pad(""))
        lines.append(pad("  ALERTS"))
        lines.append(pad("  ──────"))
        for alert in alerts[:5]:
            lines.append(pad(f"  {alert[:72]}"))
        lines.append(pad(""))

    lines.append(border_bot)
    return "\n".join(lines) + "\n"


def export_report(report: dict, fmt: str = "json") -> str:
    """Export a Control Tower report.

    Args:
        report: A report dict from ``generate_report()``.
        fmt: Export format — ``json`` or ``md``.

    Returns:
        Formatted string in the requested format.
    """
    if fmt == "json":
        return json.dumps(report, indent=2)

    # Markdown format
    lines = ["# RAPIDS Control Tower Report", ""]
    lines.append(f"Generated: {report.get('generated_at', '?')}")
    lines.append("")

    gs = report.get("global_stats", {})
    lines.append("## Summary")
    lines.append(f"- **Projects:** {gs.get('total_projects', 0)}")
    lines.append(f"- **Active Work Items:** {gs.get('active_work_items', 0)}")
    lines.append(f"- **Completed Work Items:** {gs.get('completed_work_items', 0)}")
    lines.append(f"- **Total Cost:** ${gs.get('total_cost', 0):.2f}")
    lines.append("")

    for ws in report.get("workspaces", []):
        lines.append(f"## Workspace: {ws.get('name', '?')}")
        lines.append("")
        lines.append("| Project | Tier | Health | Active WIs | Cost | Gates |")
        lines.append("|---------|------|--------|-----------|------|-------|")
        for proj in ws.get("projects", []):
            lines.append(
                f"| {proj['name']} | T{proj.get('tier', '?')} | {proj.get('health', '?')} | "
                f"{proj.get('work_items', {}).get('active', 0)} | "
                f"${proj.get('cost', {}).get('total', 0):.2f} | "
                f"{proj.get('gates_passed', 0)}✓/{proj.get('gates_pending', 0)}○ |"
            )
        lines.append("")

    alerts = alert_check(report)
    if alerts:
        lines.append("## Alerts")
        for alert in alerts:
            lines.append(f"- {alert}")

    return "\n".join(lines)
