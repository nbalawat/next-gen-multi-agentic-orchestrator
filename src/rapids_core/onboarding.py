"""Onboarding question builders for the RAPIDS start flow.

Each function returns a dict matching the AskUserQuestion tool schema,
ready to be passed directly as the tool's `questions` parameter.
"""

from __future__ import annotations


def workspace_question(existing_workspaces: list[dict] | None = None) -> dict:
    """Build the AskUserQuestion payload for workspace selection.

    Args:
        existing_workspaces: List of registered workspace dicts from the registry.

    Returns:
        A dict with a ``questions`` key containing the AskUserQuestion payload.
    """
    options = []

    if existing_workspaces:
        # Offer up to 2 existing workspaces plus "new" and "none"
        for ws in existing_workspaces[:2]:
            proj_count = len(ws.get("projects", []))
            options.append({
                "label": f"{ws['name']} (Recommended)" if len(options) == 0 else ws["name"],
                "description": f"Use existing workspace at {ws['path']} ({proj_count} project(s))",
            })

    options.append({
        "label": "Create new workspace" + (" (Recommended)" if not existing_workspaces else ""),
        "description": "Specify a directory to use as a new workspace for your projects",
    })
    options.append({
        "label": "No workspace",
        "description": "Register this project without a workspace (standalone)",
    })

    # Clamp to 4 options max
    options = options[:4]

    return {
        "questions": [
            {
                "question": "Which workspace should this project belong to?",
                "header": "Workspace",
                "multiSelect": False,
                "options": options,
            }
        ]
    }


def working_directory_question(current_dir: str = ".", workspace_path: str | None = None) -> dict:
    """Build the AskUserQuestion payload for the working directory prompt.

    Args:
        current_dir: The current working directory to offer as an option.
        workspace_path: If set, the project directory will be created under this workspace.

    Returns:
        A dict with a ``questions`` key containing the AskUserQuestion payload.
    """
    context = ""
    if workspace_path:
        context = f" (under workspace: {workspace_path})"

    return {
        "questions": [
            {
                "question": f"What is the working directory for this project{context}?",
                "header": "Directory",
                "multiSelect": False,
                "options": [
                    {
                        "label": "Current directory (Recommended)",
                        "description": f"Use the current directory: {current_dir}",
                    },
                    {
                        "label": "Existing directory",
                        "description": "Provide a path to an existing project directory",
                    },
                    {
                        "label": "Create new directory",
                        "description": (
                            f"Specify a directory name — created under {workspace_path}"
                            if workspace_path
                            else "Specify a path and RAPIDS will create it for you"
                        ),
                    },
                ],
            }
        ]
    }


def scope_confirmation_question(
    tier: int,
    tier_label: str,
    phases: list[str],
    files_impacted: int,
    integrations: list[str],
) -> dict:
    """Build the AskUserQuestion payload for scope tier confirmation.

    Args:
        tier: The classified scope tier (1-5).
        tier_label: Human-readable tier label (e.g., "Feature").
        phases: The phases that will execute for this tier.
        files_impacted: Estimated file count.
        integrations: List of integrations detected.

    Returns:
        A dict with a ``questions`` key containing the AskUserQuestion payload.
    """
    phase_list = " → ".join(p.capitalize() for p in phases)

    return {
        "questions": [
            {
                "question": (
                    f"RAPIDS classified this as Tier {tier} ({tier_label}). "
                    f"Phases: {phase_list}. "
                    f"Does this look right?"
                ),
                "header": "Scope",
                "multiSelect": False,
                "options": [
                    {
                        "label": f"Tier {tier} — {tier_label} (Recommended)",
                        "description": (
                            f"Proceed with {len(phases)} phases: {phase_list}. "
                            f"~{files_impacted} files, "
                            f"{len(integrations)} integration(s)."
                        ),
                        "preview": _scope_preview(tier, tier_label, phases, files_impacted, integrations),
                    },
                    {
                        "label": "Adjust tier up",
                        "description": "This project is more complex than estimated — bump the tier higher",
                        "preview": _tier_adjustment_preview("up", tier, phases),
                    },
                    {
                        "label": "Adjust tier down",
                        "description": "This project is simpler than estimated — lower the tier",
                        "preview": _tier_adjustment_preview("down", tier, phases),
                    },
                ],
            }
        ]
    }


def execution_mode_question(tier: int) -> dict:
    """Build the AskUserQuestion payload for execution mode selection.

    Args:
        tier: The scope tier, used to determine the recommended mode.

    Returns:
        A dict with a ``questions`` key containing the AskUserQuestion payload.
    """
    if tier <= 2:
        recommended = "Autonomous"
        rec_suffix_auto = " (Recommended)"
        rec_suffix_hybrid = ""
        rec_suffix_manual = ""
    elif tier == 3:
        recommended = "Hybrid"
        rec_suffix_auto = ""
        rec_suffix_hybrid = " (Recommended)"
        rec_suffix_manual = ""
    else:
        recommended = "Human-in-the-loop"
        rec_suffix_auto = ""
        rec_suffix_hybrid = ""
        rec_suffix_manual = " (Recommended)"

    options = [
        {
            "label": f"Autonomous{rec_suffix_auto}",
            "description": "RAPIDS runs end-to-end with auto permissions. Best for Tier 1-2.",
        },
        {
            "label": f"Hybrid{rec_suffix_hybrid}",
            "description": "Auto mode within waves, manual approval at wave boundaries. Best for Tier 3.",
        },
        {
            "label": f"Human-in-the-loop{rec_suffix_manual}",
            "description": "Manual approval for every major action. Best for Tier 4-5 and production environments.",
        },
    ]

    # Move recommended to first position
    if tier <= 2:
        pass  # Already first
    elif tier == 3:
        options[0], options[1] = options[1], options[0]
    else:
        options[0], options[2] = options[2], options[0]

    return {
        "questions": [
            {
                "question": "Which execution mode should RAPIDS use for this project?",
                "header": "Exec mode",
                "multiSelect": False,
                "options": options,
            }
        ]
    }


def project_description_question() -> dict:
    """Build the AskUserQuestion payload asking what to build.

    Returns:
        A dict with a ``questions`` key containing the AskUserQuestion payload.
    """
    return {
        "questions": [
            {
                "question": "What would you like to build? Describe your project briefly.",
                "header": "Project",
                "multiSelect": False,
                "options": [
                    {
                        "label": "New application",
                        "description": "Build a new application or service from scratch",
                    },
                    {
                        "label": "New feature",
                        "description": "Add a feature to an existing codebase",
                    },
                    {
                        "label": "Bug fix",
                        "description": "Fix a specific bug or issue",
                    },
                    {
                        "label": "Refactor / migration",
                        "description": "Refactor code, migrate infrastructure, or upgrade dependencies",
                    },
                ],
            }
        ]
    }


# ─── Preview Helpers ──────────────────────────────────────────────────────────

TIER_LABELS = {
    1: "Bug Fix",
    2: "Enhancement",
    3: "Feature",
    4: "System",
    5: "Platform",
}


def _scope_preview(
    tier: int,
    tier_label: str,
    phases: list[str],
    files_impacted: int,
    integrations: list[str],
) -> str:
    """Build a preview string for the scope confirmation question."""
    lines = [
        f"┌─────────────────────────────────────┐",
        f"│  Scope Classification               │",
        f"├─────────────────────────────────────┤",
        f"│  Tier:         {tier} — {tier_label:<20}│",
        f"│  Files:        ~{files_impacted:<23}│",
        f"│  Integrations: {len(integrations):<22}│",
        f"├─────────────────────────────────────┤",
        f"│  Phases:                            │",
    ]
    for i, phase in enumerate(phases, 1):
        marker = "→" if i == 1 else " "
        lines.append(f"│  {marker} {i}. {phase.capitalize():<30}│")
    lines.append(f"└─────────────────────────────────────┘")
    return "\n".join(lines)


def _tier_adjustment_preview(direction: str, current_tier: int, current_phases: list[str]) -> str:
    """Build a preview showing what changes with a tier adjustment."""
    from rapids_core.phase_router import route_phases

    if direction == "up":
        new_tier = min(current_tier + 1, 5)
    else:
        new_tier = max(current_tier - 1, 1)

    new_label = TIER_LABELS.get(new_tier, "Unknown")
    new_phases = route_phases(new_tier)

    lines = [
        f"┌─────────────────────────────────────┐",
        f"│  Adjusted Scope                     │",
        f"├─────────────────────────────────────┤",
        f"│  Tier {current_tier} → Tier {new_tier} ({new_label}){' ' * (18 - len(new_label))}│",
        f"│  Phases: {len(current_phases)} → {len(new_phases)}{' ' * 24}│",
        f"├─────────────────────────────────────┤",
    ]
    for i, phase in enumerate(new_phases, 1):
        lines.append(f"│  {i}. {phase.capitalize():<33}│")
    lines.append(f"└─────────────────────────────────────┘")
    return "\n".join(lines)


# ─── CLI entry point ──────────────────────────────────────────────────────────

def main() -> None:
    """CLI interface for generating onboarding question payloads as JSON."""
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: onboarding.py <command>", file=sys.stderr)
        print("Commands: working-dir, scope, exec-mode, project-desc", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    if command == "workspace":
        workspaces = None
        if not sys.stdin.isatty():
            import select as sel
            if sel.select([sys.stdin], [], [], 0.0)[0]:
                data = sys.stdin.read().strip()
                if data:
                    workspaces = json.loads(data)
        print(json.dumps(workspace_question(workspaces), indent=2))

    elif command == "working-dir":
        cwd = sys.argv[2] if len(sys.argv) > 2 else "."
        ws = sys.argv[3] if len(sys.argv) > 3 else None
        print(json.dumps(working_directory_question(cwd, workspace_path=ws), indent=2))

    elif command == "scope":
        data = json.loads(sys.stdin.read())
        print(json.dumps(scope_confirmation_question(
            tier=data["tier"],
            tier_label=data["tier_label"],
            phases=data["phases"],
            files_impacted=data.get("files_impacted", 0),
            integrations=data.get("integrations", []),
        ), indent=2))

    elif command == "exec-mode":
        tier = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        print(json.dumps(execution_mode_question(tier), indent=2))

    elif command == "project-desc":
        print(json.dumps(project_description_question(), indent=2))

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
