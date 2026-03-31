"""Phase routing: maps scope tier to the list of phases to execute."""

from __future__ import annotations

PHASE_MAP: dict[int, list[str]] = {
    1: ["implement"],
    2: ["plan", "implement"],
    3: ["analysis", "plan", "implement", "deploy"],
    4: ["research", "analysis", "plan", "implement", "deploy"],
    5: ["research", "analysis", "plan", "implement", "deploy", "sustain"],
}

ALL_PHASES = ["research", "analysis", "plan", "implement", "deploy", "sustain"]


def route_phases(tier: int) -> list[str]:
    """Return the ordered list of phases for a given scope tier.

    Args:
        tier: Scope tier (1-5).

    Returns:
        Ordered list of phase names.

    Raises:
        ValueError: If tier is not between 1 and 5.
    """
    if tier not in PHASE_MAP:
        raise ValueError(f"Invalid tier {tier}. Must be between 1 and 5.")
    return list(PHASE_MAP[tier])
