"""Project registry: tracks all RAPIDS workspaces and projects under management.

A **workspace** is a parent directory that contains multiple RAPIDS projects.
Each project lives in its own subdirectory under the workspace. The registry
tracks workspaces and their projects in a single file at ``~/.rapids/projects.json``.

Registry structure::

    {
        "workspaces": [
            {
                "name": "my-workspace",
                "path": "/home/user/my-workspace",
                "created_at": "...",
                "projects": ["proj-a", "proj-b"]
            }
        ],
        "projects": [
            {
                "name": "proj-a",
                "path": "/home/user/my-workspace/proj-a",
                "workspace": "/home/user/my-workspace",
                "tier": 3,
                "phase": "implement",
                ...
            }
        ]
    }
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REGISTRY_DIR = Path.home() / ".rapids"
REGISTRY_FILE = REGISTRY_DIR / "projects.json"


def _ensure_registry() -> dict:
    """Ensure the registry directory and file exist, return current state."""
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_FILE.exists():
        initial = {"workspaces": [], "projects": []}
        REGISTRY_FILE.write_text(json.dumps(initial, indent=2) + "\n")
        return initial
    data = json.loads(REGISTRY_FILE.read_text())
    # Migrate from old list format to new dict format
    if isinstance(data, list):
        data = {"workspaces": [], "projects": data}
        REGISTRY_FILE.write_text(json.dumps(data, indent=2) + "\n")
    if "workspaces" not in data:
        data["workspaces"] = []
    if "projects" not in data:
        data["projects"] = []
    return data


def _save_registry(registry: dict) -> None:
    """Write the registry back to disk."""
    REGISTRY_FILE.write_text(json.dumps(registry, indent=2) + "\n")


# ─── Workspace Management ────────────────────────────────────────────────────

def register_workspace(name: str, path: str) -> dict:
    """Register a new workspace or return the existing one.

    Args:
        name: Human-readable workspace name.
        path: Absolute path to the workspace directory.

    Returns:
        The workspace entry dict.
    """
    registry = _ensure_registry()
    now = datetime.now(timezone.utc).isoformat()

    for ws in registry["workspaces"]:
        if ws["path"] == path:
            ws["name"] = name
            ws["updated_at"] = now
            _save_registry(registry)
            return ws

    entry = {
        "name": name,
        "path": path,
        "created_at": now,
        "updated_at": now,
        "projects": [],
    }
    registry["workspaces"].append(entry)
    _save_registry(registry)
    return entry


def list_workspaces() -> list[dict]:
    """Return all registered workspaces."""
    registry = _ensure_registry()
    return registry["workspaces"]


def get_workspace(path: str) -> dict | None:
    """Look up a workspace by path."""
    registry = _ensure_registry()
    for ws in registry["workspaces"]:
        if ws["path"] == path:
            return ws
    return None


def get_workspace_projects(workspace_path: str) -> list[dict]:
    """Return all projects within a given workspace.

    Args:
        workspace_path: Absolute path to the workspace directory.

    Returns:
        List of project dicts belonging to this workspace.
    """
    registry = _ensure_registry()
    return [
        p for p in registry["projects"]
        if p.get("workspace") == workspace_path
    ]


def infer_workspace(project_path: str) -> str | None:
    """Infer which workspace a project path belongs to.

    Checks if the project path is a subdirectory of any registered workspace.

    Returns:
        The workspace path, or None if no match.
    """
    registry = _ensure_registry()
    proj = Path(project_path).resolve()
    for ws in registry["workspaces"]:
        ws_path = Path(ws["path"]).resolve()
        try:
            proj.relative_to(ws_path)
            return ws["path"]
        except ValueError:
            continue
    return None


# ─── Project Management ──────────────────────────────────────────────────────

def register_project(
    name: str,
    path: str,
    tier: int,
    phase: str,
    plugins: list[str] | None = None,
    workspace: str | None = None,
) -> dict:
    """Register a new project or update an existing one.

    Args:
        name: Human-readable project name / ID.
        path: Absolute path to the project working directory.
        tier: Scope tier (1-5).
        phase: Current phase name.
        plugins: Active domain plugins.
        workspace: Absolute path to the parent workspace (optional).
                   If not provided, attempts to infer from registered workspaces.

    Returns:
        The project entry dict.
    """
    registry = _ensure_registry()
    now = datetime.now(timezone.utc).isoformat()

    # Auto-infer workspace if not provided
    if workspace is None:
        workspace = infer_workspace(path)

    # Check if project at this path already exists
    for proj in registry["projects"]:
        if proj["path"] == path:
            proj["name"] = name
            proj["tier"] = tier
            proj["phase"] = phase
            proj["plugins"] = plugins or []
            proj["workspace"] = workspace
            proj["updated_at"] = now
            proj["status"] = "active"
            _save_registry(registry)
            _sync_workspace_projects(registry, workspace)
            return proj

    entry = {
        "name": name,
        "path": path,
        "workspace": workspace,
        "tier": tier,
        "phase": phase,
        "plugins": plugins or [],
        "created_at": now,
        "updated_at": now,
        "status": "active",
    }
    registry["projects"].append(entry)
    _save_registry(registry)
    _sync_workspace_projects(registry, workspace)
    return entry


def _sync_workspace_projects(registry: dict, workspace_path: str | None) -> None:
    """Keep workspace.projects list in sync with registered projects."""
    if workspace_path is None:
        return
    for ws in registry["workspaces"]:
        if ws["path"] == workspace_path:
            ws["projects"] = [
                p["name"] for p in registry["projects"]
                if p.get("workspace") == workspace_path
                and p.get("status") == "active"
            ]
            _save_registry(registry)
            return


def update_project_phase(path: str, phase: str) -> dict | None:
    """Update the phase of a registered project.

    Returns:
        The updated project entry, or None if not found.
    """
    registry = _ensure_registry()
    for proj in registry["projects"]:
        if proj["path"] == path:
            proj["phase"] = phase
            proj["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_registry(registry)
            return proj
    return None


def deactivate_project(path: str) -> dict | None:
    """Mark a project as inactive.

    Returns:
        The updated project entry, or None if not found.
    """
    registry = _ensure_registry()
    for proj in registry["projects"]:
        if proj["path"] == path:
            proj["status"] = "inactive"
            proj["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_registry(registry)
            # Update workspace project list
            workspace = proj.get("workspace")
            if workspace:
                _sync_workspace_projects(registry, workspace)
            return proj
    return None


def list_projects(
    active_only: bool = True,
    workspace: str | None = None,
) -> list[dict]:
    """Return registered projects.

    Args:
        active_only: If True, only return projects with status 'active'.
        workspace: If provided, only return projects in this workspace.

    Returns:
        List of project entry dicts.
    """
    registry = _ensure_registry()
    projects = registry["projects"]
    if active_only:
        projects = [p for p in projects if p.get("status") == "active"]
    if workspace:
        projects = [p for p in projects if p.get("workspace") == workspace]
    return projects


def get_project(path: str) -> dict | None:
    """Look up a project by its path.

    Returns:
        The project entry, or None if not found.
    """
    registry = _ensure_registry()
    for proj in registry["projects"]:
        if proj["path"] == path:
            return proj
    return None


def format_project_table(projects: list[dict]) -> str:
    """Format a list of projects as an ASCII table, grouped by workspace.

    Returns:
        Formatted table string ready for display.
    """
    if not projects:
        return "  No active RAPIDS projects found.\n"

    # Group projects by workspace
    by_workspace: dict[str, list[dict]] = {}
    for p in projects:
        ws = p.get("workspace") or "(no workspace)"
        by_workspace.setdefault(ws, []).append(p)

    lines: list[str] = []
    counter = 0

    for ws_path, ws_projects in by_workspace.items():
        # Workspace header
        if ws_path != "(no workspace)":
            lines.append(f"  ┌─ Workspace: {ws_path}")
            lines.append(f"  │")
            prefix = "  │ "
        else:
            prefix = "  "

        # Column widths within this group
        name_w = max(len(p["name"]) for p in ws_projects)
        name_w = max(name_w, 7)

        header = (
            f"{prefix}{'#':<4} {'PROJECT':<{name_w}}  {'TIER':<6} "
            f"{'PHASE':<12} {'STATUS':<10} DIRECTORY"
        )
        sep = prefix + "─" * (len(header) - len(prefix))

        lines.append(sep)
        lines.append(header)
        lines.append(sep)

        for p in ws_projects:
            counter += 1
            status_icon = "●" if p.get("status") == "active" else "○"
            lines.append(
                f"{prefix}{counter:<4} {p['name']:<{name_w}}  T{p['tier']:<5} "
                f"{p['phase']:<12} {status_icon} {p.get('status','unknown'):<8} "
                f"{p['path']}"
            )

        lines.append(sep)

        if ws_path != "(no workspace)":
            lines.append(f"  │")
            lines.append(f"  └─")

        lines.append("")

    return "\n".join(lines)


# --- CLI entry point for shell scripts ---

def main() -> None:
    """CLI interface for project registry operations."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: project-registry.sh <command> [args]", file=sys.stderr)
        print("Commands: list, register, update-phase, deactivate, get,", file=sys.stderr)
        print("          register-workspace, list-workspaces, workspace-projects", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    if command == "list":
        active_only = "--all" not in sys.argv
        workspace = None
        for i, arg in enumerate(sys.argv):
            if arg == "--workspace" and i + 1 < len(sys.argv):
                workspace = sys.argv[i + 1]
        projs = list_projects(active_only=active_only, workspace=workspace)
        print(format_project_table(projs))

    elif command == "register":
        data = json.loads(sys.stdin.read())
        entry = register_project(
            name=data["name"],
            path=data["path"],
            tier=data["tier"],
            phase=data["phase"],
            plugins=data.get("plugins", []),
            workspace=data.get("workspace"),
        )
        print(json.dumps(entry, indent=2))

    elif command == "update-phase":
        if len(sys.argv) < 4:
            print("Usage: project-registry.sh update-phase <path> <phase>", file=sys.stderr)
            sys.exit(1)
        result = update_project_phase(sys.argv[2], sys.argv[3])
        if result:
            print(json.dumps(result, indent=2))
        else:
            print("Project not found", file=sys.stderr)
            sys.exit(1)

    elif command == "deactivate":
        if len(sys.argv) < 3:
            print("Usage: project-registry.sh deactivate <path>", file=sys.stderr)
            sys.exit(1)
        result = deactivate_project(sys.argv[2])
        if result:
            print(json.dumps(result, indent=2))
        else:
            print("Project not found", file=sys.stderr)
            sys.exit(1)

    elif command == "get":
        if len(sys.argv) < 3:
            print("Usage: project-registry.sh get <path>", file=sys.stderr)
            sys.exit(1)
        result = get_project(sys.argv[2])
        if result:
            print(json.dumps(result, indent=2))
        else:
            print("Project not found", file=sys.stderr)
            sys.exit(1)

    elif command == "register-workspace":
        data = json.loads(sys.stdin.read())
        entry = register_workspace(
            name=data["name"],
            path=data["path"],
        )
        print(json.dumps(entry, indent=2))

    elif command == "list-workspaces":
        workspaces = list_workspaces()
        if not workspaces:
            print("  No workspaces registered.")
        else:
            for ws in workspaces:
                proj_count = len(ws.get("projects", []))
                print(f"  {ws['name']}: {ws['path']} ({proj_count} projects)")

    elif command == "workspace-projects":
        if len(sys.argv) < 3:
            print("Usage: project-registry.sh workspace-projects <workspace_path>", file=sys.stderr)
            sys.exit(1)
        projs = get_workspace_projects(sys.argv[2])
        print(format_project_table(projs))

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


# ─── Aliases for common naming guesses ────────────────────────────────────────
update_phase = update_project_phase
update_project = register_project
get_projects = list_projects
get_workspaces = list_workspaces


if __name__ == "__main__":
    main()
