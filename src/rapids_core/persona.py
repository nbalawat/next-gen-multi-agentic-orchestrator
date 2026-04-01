"""Persona Gatekeeping: role-based behavior and access control for RAPIDS.

Personas define what actions a user can take in which phases, which activities
they can perform, and what requires approval. This enables team-based workflows
where architects design, developers implement, and stakeholders observe.
"""

from __future__ import annotations

from pathlib import Path

import yaml

_PERSONAS_DIR = Path(__file__).parent.parent.parent / "rapids-core" / "personas"


def load_personas(personas_dir: str | Path | None = None) -> list[dict]:
    """Load persona definitions from YAML.

    Args:
        personas_dir: Directory containing personas.yaml.

    Returns:
        List of persona dicts.
    """
    if personas_dir is None:
        personas_dir = _PERSONAS_DIR

    yaml_path = Path(personas_dir) / "personas.yaml"
    if not yaml_path.exists():
        return []

    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    personas = data.get("personas", [])
    for p in personas:
        p.setdefault("allowed_phases", [])
        p.setdefault("allowed_actions", [])
        p.setdefault("denied_actions", [])
        p.setdefault("can_delegate_to", [])
        p.setdefault("approval_required_for", [])

    return personas


def get_persona(persona_id: str, personas_dir: str | Path | None = None) -> dict | None:
    """Get a specific persona by ID.

    Args:
        persona_id: The persona ID (e.g., "architect").
        personas_dir: Directory containing personas.yaml.

    Returns:
        The persona dict, or None if not found.
    """
    for p in load_personas(personas_dir):
        if p["id"] == persona_id:
            return p
    return None


def set_active_persona(config: dict, persona_id: str) -> dict:
    """Set the active persona in the rapids.json config.

    Args:
        config: The rapids.json dict.
        persona_id: The persona ID to activate.

    Returns:
        The updated config dict.

    Raises:
        ValueError: If persona_id is not valid.
    """
    persona = get_persona(persona_id)
    if persona is None:
        valid = [p["id"] for p in load_personas()]
        raise ValueError(f"Unknown persona '{persona_id}'. Valid: {valid}")

    config["active_persona"] = persona_id
    return config


def get_active_persona(config: dict) -> dict | None:
    """Get the currently active persona from config.

    Args:
        config: The rapids.json dict.

    Returns:
        The persona dict, or None if not set (defaults to lead).
    """
    persona_id = config.get("active_persona", "lead")
    return get_persona(persona_id)


def check_permission(
    persona: dict,
    action: str,
    phase: str | None = None,
    activity_id: str | None = None,
) -> dict:
    """Check if a persona has permission for an action.

    Args:
        persona: The persona dict.
        action: The action to check (e.g., "implement", "approve_gate").
        phase: Optional phase context.
        activity_id: Optional activity context.

    Returns:
        Dict with keys: allowed (bool), reason (str).
    """
    # Check denied actions first (deny overrides allow)
    if action in persona.get("denied_actions", []):
        return {
            "allowed": False,
            "reason": f"{persona['name']} cannot perform '{action}'",
        }

    # Check phase access
    if phase and persona.get("allowed_phases"):
        if phase not in persona["allowed_phases"]:
            return {
                "allowed": False,
                "reason": f"{persona['name']} cannot operate in '{phase}' phase",
            }

    # Check if approval is required (approval_required_for implies allowed with gate)
    approval_for = persona.get("approval_required_for", [])
    if action in approval_for:
        return {
            "allowed": True,
            "reason": f"Allowed but requires approval for '{action}'",
            "requires_approval": True,
        }

    # Check allowed actions
    allowed_actions = persona.get("allowed_actions", [])
    if allowed_actions and action not in allowed_actions:
        return {
            "allowed": False,
            "reason": f"{persona['name']} is not authorized for '{action}'",
        }

    # Legacy check (redundant after refactor but kept for safety)
    if action in approval_for:
        return {
            "allowed": True,
            "reason": f"Allowed but requires approval for '{action}'",
            "requires_approval": True,
        }

    return {"allowed": True, "reason": "Permitted"}


def get_allowed_activities(
    persona: dict,
    phase: str,
    all_activities: list[dict],
) -> list[dict]:
    """Filter activities to those the persona can perform.

    Args:
        persona: The persona dict.
        phase: The current phase.
        all_activities: Full list of activities for this phase.

    Returns:
        Filtered list of activities the persona can work on.
    """
    # Check phase access first
    if phase not in persona.get("allowed_phases", []):
        return []

    allowed = persona.get("allowed_activities", ["*"])
    if "*" in allowed:
        return all_activities

    return [a for a in all_activities if a["id"] in allowed]


def can_delegate(persona: dict, to_persona_id: str) -> bool:
    """Check if a persona can delegate to another.

    Args:
        persona: The delegating persona.
        to_persona_id: The target persona ID.

    Returns:
        True if delegation is allowed.
    """
    return to_persona_id in persona.get("can_delegate_to", [])


def format_persona_badge(persona: dict) -> str:
    """Format a persona as a display badge for banners.

    Args:
        persona: The persona dict.

    Returns:
        Formatted badge string like ``[Architect]``.
    """
    return f"[{persona.get('name', '?')}]"


def build_persona_selection_question(
    personas: list[dict] | None = None,
) -> dict:
    """Build an AskUserQuestion payload for persona selection.

    Args:
        personas: List of persona dicts. Loaded from YAML if not provided.

    Returns:
        AskUserQuestion payload dict.
    """
    if personas is None:
        personas = load_personas()

    options = []
    for p in personas[:4]:
        options.append({
            "label": f"{p['name']}" + (" (Recommended)" if p["id"] == "lead" else ""),
            "description": p.get("description", ""),
        })

    return {
        "questions": [
            {
                "question": "What is your role on this project?",
                "header": "Role",
                "multiSelect": False,
                "options": options,
            }
        ]
    }
