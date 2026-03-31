"""ASCII art banners for RAPIDS framework — phase and activity visualization."""

from __future__ import annotations

# ─── Main RAPIDS Logo ────────────────────────────────────────────────────────

RAPIDS_LOGO = r"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ██████╗   █████╗  ██████╗  ██╗ ██████╗  ███████╗                          ║
║   ██╔══██╗ ██╔══██╗ ██╔══██╗ ██║ ██╔══██╗ ██╔════╝                          ║
║   ██████╔╝ ███████║ ██████╔╝ ██║ ██║  ██║ ███████╗                          ║
║   ██╔══██╗ ██╔══██║ ██╔═══╝  ██║ ██║  ██║ ╚════██║                          ║
║   ██║  ██║ ██║  ██║ ██║      ██║ ██████╔╝ ███████║                          ║
║   ╚═╝  ╚═╝ ╚═╝  ╚═╝ ╚═╝      ╚═╝ ╚═════╝  ╚══════╝                          ║
║                                                                              ║
║   Requirements · Architecture · Planning · Implementation · Deployment · S   ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# Compact logo for inline use
RAPIDS_LOGO_COMPACT = r"""
 ┌─────────────────────────────────────────────────────────┐
 │  ╦═╗ ╔═╗ ╔═╗ ╦ ╔╦╗ ╔═╗    Orchestration Framework     │
 │  ╠╦╝ ╠═╣ ╠═╝ ║  ║║ ╚═╗    v1.0.0                      │
 │  ╩╚═ ╩ ╩ ╩   ╩ ═╩╝ ╚═╝                                │
 └─────────────────────────────────────────────────────────┘
"""

# ─── Phase Definitions ───────────────────────────────────────────────────────

PHASE_LABELS = {
    "research":  ("R", "RESEARCH",       "Deep problem understanding & domain exploration"),
    "analysis":  ("A", "ARCHITECTURE",   "Solution design & technology decisions"),
    "plan":      ("P", "PLANNING",       "Feature specs, dependency graphs & wave computation"),
    "implement": ("I", "IMPLEMENTATION", "Code, test, commit — one criterion at a time"),
    "deploy":    ("D", "DEPLOYMENT",     "Ship it, smoke test, verify"),
    "sustain":   ("S", "STABILIZATION",  "Monitoring, alerting & operational runbooks"),
}

ALL_PHASE_KEYS = ["research", "analysis", "plan", "implement", "deploy", "sustain"]


def _phase_bar(current_phase: str, phases_in_scope: list[str] | None = None) -> str:
    """Build a horizontal phase progress bar.

    Active phase is highlighted with block characters.
    Completed phases show a checkmark.
    Future phases are dimmed.
    Out-of-scope phases are shown as dots.
    """
    if phases_in_scope is None:
        phases_in_scope = ALL_PHASE_KEYS

    # Determine completed vs current vs future
    phase_order = {p: i for i, p in enumerate(ALL_PHASE_KEYS)}
    current_idx = phase_order.get(current_phase, -1)

    cells = []
    for phase_key in ALL_PHASE_KEYS:
        short, label, _ = PHASE_LABELS[phase_key]
        idx = phase_order[phase_key]
        in_scope = phase_key in phases_in_scope

        if not in_scope:
            cells.append(f"  · {label:<16} ·  ")
        elif idx < current_idx:
            cells.append(f"  ✓ {label:<16} ✓  ")
        elif idx == current_idx:
            cells.append(f"  ▶ {label:<16} ◀  ")
        else:
            cells.append(f"  ○ {label:<16} ○  ")

    return cells


def phase_banner(
    current_phase: str,
    activity: str = "",
    tier: int = 0,
    project_name: str = "",
    phases_in_scope: list[str] | None = None,
) -> str:
    """Generate a full-width ASCII banner showing the current RAPIDS phase and activity.

    Args:
        current_phase: The active phase key (e.g., 'implement').
        activity: Description of what we're about to do (e.g., 'Wave 2 — Feature F003').
        tier: Scope tier (1-5).
        project_name: Project name/ID.
        phases_in_scope: Which phases apply for this tier.

    Returns:
        Multi-line ASCII art string.
    """
    if phases_in_scope is None:
        phases_in_scope = ALL_PHASE_KEYS

    _, phase_label, phase_desc = PHASE_LABELS.get(
        current_phase, ("?", "UNKNOWN", "Unknown phase")
    )

    # Build the phase pipeline visualization
    phase_order = {p: i for i, p in enumerate(ALL_PHASE_KEYS)}
    current_idx = phase_order.get(current_phase, -1)

    pipeline_parts = []
    for phase_key in ALL_PHASE_KEYS:
        short, label, _ = PHASE_LABELS[phase_key]
        idx = phase_order[phase_key]
        in_scope = phase_key in phases_in_scope

        if not in_scope:
            pipeline_parts.append(f" ·{short}· ")
        elif idx < current_idx:
            pipeline_parts.append(f" ✓{short}✓ ")
        elif idx == current_idx:
            pipeline_parts.append(f"▐█{short}█▌")
        else:
            pipeline_parts.append(f" ○{short}○ ")

    pipeline = "──".join(pipeline_parts)

    # Construct the banner
    w = 78
    border_top = "╔" + "═" * w + "╗"
    border_bot = "╚" + "═" * w + "╝"
    border_mid = "╠" + "═" * w + "╣"
    border_thin = "╟" + "─" * w + "╢"

    def pad(text: str) -> str:
        """Pad text to fit within the border, accounting for unicode widths."""
        # Simple approach: pad to width
        visible = text
        padding = max(0, w - _visible_len(visible))
        return "║ " + visible + " " * (padding - 1) + "║"

    lines = []
    lines.append(border_top)
    lines.append(pad(""))

    # Title line
    title = f"R A P I D S  —  {phase_label} PHASE"
    title_padding = (w - 2 - len(title)) // 2
    title_line = " " * title_padding + title
    lines.append(pad(title_line))

    lines.append(pad(""))

    # Phase pipeline
    lines.append(border_thin)
    lines.append(pad(""))
    lines.append(pad(f"  {pipeline}"))
    lines.append(pad(""))

    # Phase legend
    for phase_key in ALL_PHASE_KEYS:
        idx = phase_order[phase_key]
        short, label, desc = PHASE_LABELS[phase_key]
        in_scope = phase_key in phases_in_scope

        if phase_key == current_phase:
            lines.append(pad(f"  ▶ [{short}] {label:<16} {desc}"))
        elif in_scope and idx < current_idx:
            lines.append(pad(f"  ✓ [{short}] {label:<16} (completed)"))
        elif in_scope:
            lines.append(pad(f"  ○ [{short}] {label:<16} (upcoming)"))
        else:
            lines.append(pad(f"  · [{short}] {label:<16} (not in scope)"))

    lines.append(pad(""))
    lines.append(border_thin)
    lines.append(pad(""))

    # Project info
    if project_name:
        lines.append(pad(f"  Project:  {project_name}"))
    if tier:
        tier_labels = {
            1: "Bug Fix",
            2: "Enhancement",
            3: "Feature",
            4: "System",
            5: "Platform",
        }
        lines.append(pad(f"  Tier:     {tier} — {tier_labels.get(tier, 'Unknown')}"))

    # Activity line (the big one the user wants to see)
    if activity:
        lines.append(pad(""))
        lines.append(border_thin)
        lines.append(pad(""))
        lines.append(pad(f"  ┌{'─' * 60}┐"))
        lines.append(pad(f"  │  CURRENT ACTIVITY:                                        │"))
        # Wrap activity text if needed
        act_lines = _wrap_text(activity, 56)
        for al in act_lines:
            lines.append(pad(f"  │  {al:<58}│"))
        lines.append(pad(f"  └{'─' * 60}┘"))

    lines.append(pad(""))
    lines.append(border_bot)

    return "\n".join(lines) + "\n"


def welcome_banner(
    projects: list[dict] | None = None,
    workspaces: list[dict] | None = None,
) -> str:
    """Generate the welcome screen shown on ``rapid start``.

    Args:
        projects: List of active project dicts (from project registry).
        workspaces: List of workspace dicts (from project registry).

    Returns:
        Multi-line ASCII art string with logo and workspace/project listing.
    """
    w = 78
    border_top = "╔" + "═" * w + "╗"
    border_bot = "╚" + "═" * w + "╝"
    border_thin = "╟" + "─" * w + "╢"

    def pad(text: str) -> str:
        padding = max(0, w - _visible_len(text) - 1)
        return "║ " + text + " " * padding + "║"

    lines = []
    lines.append(border_top)
    lines.append(pad(""))

    # Inline logo
    logo_lines = [
        "   ██████╗   █████╗  ██████╗  ██╗ ██████╗  ███████╗",
        "   ██╔══██╗ ██╔══██╗ ██╔══██╗ ██║ ██╔══██╗ ██╔════╝",
        "   ██████╔╝ ███████║ ██████╔╝ ██║ ██║  ██║ ███████╗",
        "   ██╔══██╗ ██╔══██║ ██╔═══╝  ██║ ██║  ██║ ╚════██║",
        "   ██║  ██║ ██║  ██║ ██║      ██║ ██████╔╝ ███████║",
        "   ╚═╝  ╚═╝ ╚═╝  ╚═╝ ╚═╝      ╚═╝ ╚═════╝  ╚══════╝",
    ]
    for ll in logo_lines:
        lines.append(pad(ll))

    lines.append(pad(""))
    lines.append(pad("   Requirements · Architecture · Planning · Implementation · Deployment · S"))
    lines.append(pad(""))
    lines.append(pad("   Orchestration Framework v1.0.0"))
    lines.append(pad(""))
    lines.append(border_thin)

    # Workspaces & Projects section
    lines.append(pad(""))
    lines.append(pad("  WORKSPACES & PROJECTS"))
    lines.append(pad("  ─────────────────────"))
    lines.append(pad(""))

    has_content = False

    if workspaces:
        # Group projects by workspace
        projects_by_ws: dict[str, list[dict]] = {}
        standalone: list[dict] = []

        if projects:
            for p in projects:
                ws = p.get("workspace")
                if ws:
                    projects_by_ws.setdefault(ws, []).append(p)
                else:
                    standalone.append(p)

        for ws in workspaces:
            ws_path = ws["path"]
            ws_name = ws["name"]
            ws_projs = projects_by_ws.get(ws_path, [])
            proj_count = len(ws_projs)
            has_content = True

            lines.append(pad(f"  ┌─ Workspace: {ws_name}"))
            lines.append(pad(f"  │  Path: {ws_path}"))
            lines.append(pad(f"  │  Projects: {proj_count}"))
            lines.append(pad(f"  │"))

            if ws_projs:
                for i, p in enumerate(ws_projs):
                    is_last = i == len(ws_projs) - 1
                    branch = "└──" if is_last else "├──"
                    status_icon = "●" if p.get("status") == "active" else "○"
                    name = p["name"][:20]
                    phase = p.get("phase", "?")
                    tier = p.get("tier", 0)
                    lines.append(pad(
                        f"  │  {branch} {status_icon} {name:<20} T{tier}  {phase}"
                    ))
            else:
                lines.append(pad(f"  │  └── (no projects yet)"))

            lines.append(pad(f"  │"))
            lines.append(pad(f"  └─"))
            lines.append(pad(""))

        # Show standalone projects (not in any workspace)
        if standalone:
            lines.append(pad("  Standalone Projects (no workspace):"))
            for p in standalone:
                status_icon = "●" if p.get("status") == "active" else "○"
                name = p["name"][:20]
                phase = p.get("phase", "?")
                tier = p.get("tier", 0)
                path = p["path"]
                if len(path) > 30:
                    path = "..." + path[-27:]
                lines.append(pad(f"    {status_icon} {name:<20} T{tier}  {phase:<12} {path}"))
            lines.append(pad(""))
            has_content = True

    elif projects:
        # No workspaces registered, just show flat project list
        has_content = True
        lines.append(pad(f"  {'#':<4} {'PROJECT':<20} {'TIER':<8} {'PHASE':<14} {'STATUS':<10} DIRECTORY"))
        lines.append(pad("  " + "─" * 72))
        for i, p in enumerate(projects, 1):
            status_icon = "●" if p.get("status") == "active" else "○"
            name = p["name"][:18]
            path = p["path"]
            if len(path) > 28:
                path = "..." + path[-25:]
            line = f"  {i:<4} {name:<20} T{p['tier']:<7} {p['phase']:<14} {status_icon} {p.get('status','?'):<8} {path}"
            lines.append(pad(line))
        lines.append(pad(""))

    if not has_content:
        lines.append(pad("  No workspaces or projects yet. Let's set one up!"))
        lines.append(pad(""))

    lines.append(border_thin)
    lines.append(pad(""))
    lines.append(pad("  To begin, you'll be asked to:"))
    lines.append(pad("    1. Select or create a workspace"))
    lines.append(pad("    2. Specify the project working directory"))
    lines.append(pad("    3. Describe what you want to build"))
    lines.append(pad(""))
    lines.append(border_bot)

    return "\n".join(lines) + "\n"


def transition_banner(from_phase: str, to_phase: str, project_name: str = "") -> str:
    """Generate a phase transition banner.

    Args:
        from_phase: Phase we're leaving.
        to_phase: Phase we're entering.
        project_name: Project name/ID.

    Returns:
        Multi-line ASCII art string.
    """
    w = 78
    border_top = "╔" + "═" * w + "╗"
    border_bot = "╚" + "═" * w + "╝"

    def pad(text: str) -> str:
        padding = max(0, w - _visible_len(text) - 1)
        return "║ " + text + " " * padding + "║"

    _, from_label, _ = PHASE_LABELS.get(from_phase, ("?", "UNKNOWN", ""))
    _, to_label, to_desc = PHASE_LABELS.get(to_phase, ("?", "UNKNOWN", ""))

    lines = []
    lines.append(border_top)
    lines.append(pad(""))
    lines.append(pad(f"  ╔══════════════════════════════════════════════════════════════════╗"))
    lines.append(pad(f"  ║                                                                  ║"))
    lines.append(pad(f"  ║   PHASE TRANSITION                                               ║"))
    lines.append(pad(f"  ║                                                                  ║"))
    lines.append(pad(f"  ║   {from_label:>16}  ━━━━▶  {to_label:<16}                        ║"))
    lines.append(pad(f"  ║                                                                  ║"))
    lines.append(pad(f"  ╚══════════════════════════════════════════════════════════════════╝"))
    lines.append(pad(""))

    if project_name:
        lines.append(pad(f"  Project: {project_name}"))
    lines.append(pad(f"  Entering: {to_label} — {to_desc}"))
    lines.append(pad(""))
    lines.append(border_bot)

    return "\n".join(lines) + "\n"


def activity_banner(phase: str, activity: str) -> str:
    """Generate a compact activity-focus banner.

    Args:
        phase: Current phase key.
        activity: What we're about to work on.

    Returns:
        Multi-line ASCII art string.
    """
    _, phase_label, _ = PHASE_LABELS.get(phase, ("?", "UNKNOWN", ""))

    w = 70
    lines = []
    lines.append(f"┌{'─' * w}┐")
    lines.append(f"│{'':^{w}}│")
    lines.append(f"│{'R A P I D S':^{w}}│")
    lines.append(f"│{f'── {phase_label} PHASE ──':^{w}}│")
    lines.append(f"│{'':^{w}}│")
    lines.append(f"├{'─' * w}┤")
    lines.append(f"│{'':^{w}}│")

    act_lines = _wrap_text(activity, w - 6)
    for al in act_lines:
        lines.append(f"│   {al:<{w - 3}}│")

    lines.append(f"│{'':^{w}}│")
    lines.append(f"└{'─' * w}┘")

    return "\n".join(lines) + "\n"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _visible_len(text: str) -> int:
    """Approximate visible length of a string with unicode box-drawing chars.

    This is a simplification — full-width chars (CJK, some box-drawing)
    would need a proper wcwidth library. For our ASCII art this is fine.
    """
    return len(text)


def _wrap_text(text: str, width: int) -> list[str]:
    """Simple word-wrap to a given width."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        elif current:
            current += " " + word
        else:
            current = word
    if current:
        lines.append(current)
    return lines or [""]


# ─── CLI entry point ──────────────────────────────────────────────────────────

def main() -> None:
    """CLI interface for ASCII banner generation."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: ascii-banner.sh <command> [args]", file=sys.stderr)
        print("Commands: welcome, phase, transition, activity", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    if command == "welcome":
        # Optionally read projects from stdin as JSON
        import select
        projects = None
        if select.select([sys.stdin], [], [], 0.0)[0]:
            data = sys.stdin.read().strip()
            if data:
                projects = json.loads(data)
        print(welcome_banner(projects))

    elif command == "phase":
        # Read config from stdin JSON
        import json
        data = json.loads(sys.stdin.read())
        print(phase_banner(
            current_phase=data["phase"],
            activity=data.get("activity", ""),
            tier=data.get("tier", 0),
            project_name=data.get("project_name", ""),
            phases_in_scope=data.get("phases_in_scope"),
        ))

    elif command == "transition":
        import json
        data = json.loads(sys.stdin.read())
        print(transition_banner(
            from_phase=data["from_phase"],
            to_phase=data["to_phase"],
            project_name=data.get("project_name", ""),
        ))

    elif command == "activity":
        import json
        data = json.loads(sys.stdin.read())
        print(activity_banner(
            phase=data["phase"],
            activity=data["activity"],
        ))

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    import json
    main()
