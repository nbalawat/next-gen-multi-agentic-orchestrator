"""AskUserQuestion payload builders for phase-level interactions.

Used by the /rapids-core:go skill and other phase-driven interactions.
Each function returns a dict matching the AskUserQuestion tool schema.
"""

from __future__ import annotations


def phase_transition_question(
    current_phase: str,
    next_phase: str,
) -> dict:
    """Build the AskUserQuestion payload for confirming a phase transition.

    Args:
        current_phase: The phase we're leaving.
        next_phase: The phase we're entering.

    Returns:
        AskUserQuestion payload dict.
    """
    return {
        "questions": [
            {
                "question": (
                    f"Phase gate passed. Ready to advance from "
                    f"{current_phase.capitalize()} to {next_phase.capitalize()}. Proceed?"
                ),
                "header": "Advance",
                "multiSelect": False,
                "options": [
                    {
                        "label": f"Advance to {next_phase.capitalize()} (Recommended)",
                        "description": "All gate conditions met. Move to the next phase.",
                    },
                    {
                        "label": "Stay in current phase",
                        "description": f"Continue working in {current_phase.capitalize()} before advancing",
                    },
                    {
                        "label": "Skip to a different phase",
                        "description": "Jump to a specific phase (e.g., skip analysis for a quick prototype)",
                    },
                ],
            }
        ]
    }


def wave_plan_question(num_waves: int, num_features: int) -> dict:
    """Build the AskUserQuestion payload for wave plan confirmation.

    Args:
        num_waves: Total number of waves computed.
        num_features: Total number of features across all waves.

    Returns:
        AskUserQuestion payload dict.
    """
    return {
        "questions": [
            {
                "question": (
                    f"Wave plan computed: {num_waves} wave(s), "
                    f"{num_features} total feature(s). How should we proceed?"
                ),
                "header": "Wave plan",
                "multiSelect": False,
                "options": [
                    {
                        "label": "Execute all waves (Recommended)",
                        "description": "Run all waves sequentially with the configured execution mode",
                    },
                    {
                        "label": "Execute wave by wave",
                        "description": "Pause for approval between each wave",
                    },
                    {
                        "label": "Execute single wave",
                        "description": "Run only Wave 1, then stop for review",
                    },
                ],
            }
        ]
    }


def wave_boundary_question(
    completed_wave: int,
    next_wave: int,
    features_passed: int,
    features_total: int,
) -> dict:
    """Build the AskUserQuestion payload for wave boundary approval.

    Args:
        completed_wave: The wave number just completed.
        next_wave: The next wave number.
        features_passed: How many features passed in the completed wave.
        features_total: Total features in the completed wave.

    Returns:
        AskUserQuestion payload dict.
    """
    return {
        "questions": [
            {
                "question": (
                    f"Wave {completed_wave} complete "
                    f"({features_passed}/{features_total} features passed). "
                    f"Ready to start Wave {next_wave}?"
                ),
                "header": "Next wave",
                "multiSelect": False,
                "options": [
                    {
                        "label": f"Start Wave {next_wave} (Recommended)",
                        "description": f"All features in Wave {completed_wave} passed. Proceed to the next wave.",
                    },
                    {
                        "label": f"Review Wave {completed_wave} results first",
                        "description": "Show detailed results before continuing",
                    },
                    {
                        "label": "Stop here",
                        "description": "Pause execution. Resume later with /rapids-core:go",
                    },
                ],
            }
        ]
    }


def evaluator_failure_question(feature_id: str, max_retries: int = 3) -> dict:
    """Build the AskUserQuestion payload for evaluator failure handling.

    Args:
        feature_id: The feature ID that failed (e.g., "F003").
        max_retries: How many retries were attempted.

    Returns:
        AskUserQuestion payload dict.
    """
    return {
        "questions": [
            {
                "question": (
                    f"Feature {feature_id} failed evaluation after "
                    f"{max_retries} attempts. How should we proceed?"
                ),
                "header": "Failed",
                "multiSelect": False,
                "options": [
                    {
                        "label": "Retry with different approach",
                        "description": "Generator will attempt the feature with a fresh strategy",
                    },
                    {
                        "label": "Skip and continue",
                        "description": "Skip this feature and proceed with the next one in the wave",
                    },
                    {
                        "label": "Stop for manual intervention",
                        "description": "Pause execution so you can investigate and fix manually",
                    },
                ],
            }
        ]
    }


def deploy_target_question() -> dict:
    """Build the AskUserQuestion payload for deployment target selection.

    Returns:
        AskUserQuestion payload dict.
    """
    return {
        "questions": [
            {
                "question": "Ready to deploy. Which environment should we target?",
                "header": "Deploy to",
                "multiSelect": False,
                "options": [
                    {
                        "label": "Staging (Recommended)",
                        "description": "Deploy to staging environment for verification first",
                    },
                    {
                        "label": "Production",
                        "description": "Deploy directly to production",
                    },
                    {
                        "label": "Local / Docker",
                        "description": "Deploy locally for smoke testing",
                    },
                ],
            }
        ]
    }


def research_focus_question(phase: str = "research") -> dict:
    """Build the AskUserQuestion payload for research/analysis focus areas.

    Args:
        phase: The phase name (research or analysis).

    Returns:
        AskUserQuestion payload dict.
    """
    return {
        "questions": [
            {
                "question": f"Entering {phase.capitalize()}. What areas should we focus on?",
                "header": "Focus",
                "multiSelect": True,
                "options": [
                    {
                        "label": "Domain research",
                        "description": "Explore the problem domain, existing solutions, and best practices",
                    },
                    {
                        "label": "Technical constraints",
                        "description": "Identify infrastructure, performance, and compliance constraints",
                    },
                    {
                        "label": "Stakeholder requirements",
                        "description": "Clarify user needs, business rules, and acceptance criteria",
                    },
                    {
                        "label": "Risk assessment",
                        "description": "Identify technical risks and potential blockers",
                    },
                ],
            }
        ]
    }
