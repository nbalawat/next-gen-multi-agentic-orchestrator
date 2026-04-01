"""Knowledge Fabric: agent expertise accumulation via ACT → LEARN → REUSE.

Agents maintain YAML expertise files as mental models — working memory
validated against code, not documentation. Expertise grows from real
session outcomes and is injected into future agent prompts automatically.

Adopts principles from github.com/disler/agent-experts:
- Expertise = mental model (code is source of truth)
- Self-improve prompts let agents update their own expertise
- Line limits (1000 max) force focus on high-value knowledge
- YAML format: hierarchical, concrete, file-referenced
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

AGENTS_DIR = Path.home() / ".rapids" / "agents"
MAX_EXPERTISE_LINES = 1000


def _agent_dir(agent_name: str) -> Path:
    return AGENTS_DIR / agent_name


def _expertise_path(agent_name: str) -> Path:
    return _agent_dir(agent_name) / "expertise.yaml"


def load_agent_expertise(agent_name: str) -> dict | None:
    """Load an agent's expertise mental model from YAML.

    Args:
        agent_name: The agent name (e.g., ``terraform-engineer``).

    Returns:
        The expertise dict, or None if no expertise file exists.
    """
    path = _expertise_path(agent_name)
    if not path.exists():
        return None
    with open(path) as f:
        return yaml.safe_load(f) or {}


def save_agent_expertise(agent_name: str, expertise: dict) -> None:
    """Save an agent's expertise, enforcing the line limit.

    Args:
        agent_name: The agent name.
        expertise: The expertise dict to save.
    """
    expertise["updated_at"] = datetime.now(timezone.utc).isoformat()

    agent_dir = _agent_dir(agent_name)
    agent_dir.mkdir(parents=True, exist_ok=True)

    content = yaml.dump(expertise, default_flow_style=False, sort_keys=False)

    # Enforce line limit
    lines = content.split("\n")
    if len(lines) > MAX_EXPERTISE_LINES:
        expertise = trim_expertise(expertise)
        content = yaml.dump(expertise, default_flow_style=False, sort_keys=False)

    _expertise_path(agent_name).write_text(content)


def initialize_agent_expertise(
    agent_name: str,
    agent_definition: dict | None = None,
) -> dict:
    """Bootstrap expertise from an agent's definition (YAML frontmatter).

    Creates a starter expertise file if one doesn't exist.

    Args:
        agent_name: The agent name.
        agent_definition: Parsed frontmatter from the agent .md file.

    Returns:
        The initialized expertise dict.
    """
    existing = load_agent_expertise(agent_name)
    if existing:
        return existing

    if agent_definition is None:
        agent_definition = {}

    expertise = {
        "overview": {
            "agent_name": agent_name,
            "description": agent_definition.get("description", ""),
            "model": agent_definition.get("model", "sonnet"),
            "role": agent_definition.get("role", "coder"),
            "phase": agent_definition.get("phase", "implement"),
            "total_sessions": 0,
            "total_features": 0,
            "success_rate": 0.0,
        },
        "domain_knowledge": {},
        "common_pitfalls": [],
        "learned_lessons": [],
        "performance_stats": {
            "features_completed": 0,
            "features_failed": 0,
            "total_retries": 0,
            "first_pass_rate": 0.0,
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    save_agent_expertise(agent_name, expertise)
    return expertise


def record_session_outcome(
    agent_name: str,
    features_passed: int = 0,
    features_failed: int = 0,
    total_retries: int = 0,
    session_id: str = "",
) -> dict:
    """Record session outcomes to update agent performance stats.

    Args:
        agent_name: The agent name.
        features_passed: Number of features that passed evaluation.
        features_failed: Number that failed after max retries.
        total_retries: Total retry attempts across all features.
        session_id: The session ID for tracking.

    Returns:
        The updated expertise dict.
    """
    expertise = load_agent_expertise(agent_name)
    if expertise is None:
        expertise = initialize_agent_expertise(agent_name)

    overview = expertise.get("overview", {})
    stats = expertise.get("performance_stats", {})

    # Update counts
    overview["total_sessions"] = overview.get("total_sessions", 0) + 1
    total_features = features_passed + features_failed
    overview["total_features"] = overview.get("total_features", 0) + total_features

    stats["features_completed"] = stats.get("features_completed", 0) + features_passed
    stats["features_failed"] = stats.get("features_failed", 0) + features_failed
    stats["total_retries"] = stats.get("total_retries", 0) + total_retries

    # Recalculate rates
    total_completed = stats["features_completed"]
    total_all = total_completed + stats["features_failed"]
    if total_all > 0:
        overview["success_rate"] = round(total_completed / total_all, 3)
        stats["first_pass_rate"] = round(
            max(0, total_completed - stats["total_retries"]) / max(1, total_all), 3
        )

    expertise["overview"] = overview
    expertise["performance_stats"] = stats

    save_agent_expertise(agent_name, expertise)
    return expertise


def add_lesson(
    agent_name: str,
    lesson: str,
    source: str = "",
    confidence: float = 0.5,
) -> dict:
    """Add a learned lesson to the agent's expertise.

    If the lesson already exists (fuzzy match on first 50 chars), reinforces
    it by bumping confidence and adding the source.

    Args:
        agent_name: The agent name.
        lesson: The lesson text.
        source: Where this was learned (session ID, feature ID, etc.).
        confidence: Initial confidence score (0.0 to 1.0).

    Returns:
        The updated expertise dict.
    """
    expertise = load_agent_expertise(agent_name)
    if expertise is None:
        expertise = initialize_agent_expertise(agent_name)

    lessons = expertise.get("learned_lessons", [])
    lesson_prefix = lesson[:50].lower()

    # Check for existing similar lesson
    for existing in lessons:
        if existing.get("lesson", "")[:50].lower() == lesson_prefix:
            # Reinforce: bump confidence, add source
            existing["confidence"] = min(1.0, existing.get("confidence", 0.5) + 0.1)
            existing["times_reinforced"] = existing.get("times_reinforced", 1) + 1
            sources = existing.get("learned_from", [])
            if source and source not in sources:
                sources.append(source)
            existing["learned_from"] = sources
            expertise["learned_lessons"] = lessons
            save_agent_expertise(agent_name, expertise)
            return expertise

    # New lesson
    lessons.append({
        "lesson": lesson,
        "confidence": confidence,
        "times_reinforced": 1,
        "learned_from": [source] if source else [],
        "added_at": datetime.now(timezone.utc).isoformat(),
    })

    expertise["learned_lessons"] = lessons
    save_agent_expertise(agent_name, expertise)
    return expertise


def add_pitfall(
    agent_name: str,
    pitfall: str,
    mitigation: str,
) -> dict:
    """Add a common pitfall with its mitigation to expertise.

    If the pitfall already exists, increments its occurrence count.

    Args:
        agent_name: The agent name.
        pitfall: Description of the pitfall.
        mitigation: How to avoid or fix it.

    Returns:
        The updated expertise dict.
    """
    expertise = load_agent_expertise(agent_name)
    if expertise is None:
        expertise = initialize_agent_expertise(agent_name)

    pitfalls = expertise.get("common_pitfalls", [])
    pitfall_prefix = pitfall[:50].lower()

    for existing in pitfalls:
        if existing.get("pitfall", "")[:50].lower() == pitfall_prefix:
            existing["occurrences"] = existing.get("occurrences", 1) + 1
            existing["mitigation"] = mitigation  # Update with latest
            expertise["common_pitfalls"] = pitfalls
            save_agent_expertise(agent_name, expertise)
            return expertise

    pitfalls.append({
        "pitfall": pitfall,
        "mitigation": mitigation,
        "occurrences": 1,
    })

    expertise["common_pitfalls"] = pitfalls
    save_agent_expertise(agent_name, expertise)
    return expertise


def get_prompt_injections(agent_name: str) -> str:
    """Format expertise as a prompt section for injection into agent prompts.

    Returns high-confidence lessons and pitfalls formatted for inclusion
    in feature prompts or CLAUDE.md.

    Args:
        agent_name: The agent name.

    Returns:
        Formatted string ready for prompt injection, or empty string
        if no expertise exists.
    """
    expertise = load_agent_expertise(agent_name)
    if expertise is None:
        return ""

    lines: list[str] = []

    # Overview stats
    overview = expertise.get("overview", {})
    sessions = overview.get("total_sessions", 0)
    if sessions > 0:
        rate = overview.get("success_rate", 0)
        lines.append(f"## Your Expertise ({sessions} prior sessions, {rate:.0%} success rate)")
        lines.append("")

    # Domain knowledge (top entries)
    domain = expertise.get("domain_knowledge", {})
    if domain:
        lines.append("### Domain Knowledge")
        for category, entries in domain.items():
            if isinstance(entries, dict):
                for key, val in entries.items():
                    if isinstance(val, dict) and "pattern" in val:
                        conf = val.get("confidence", 0)
                        if conf >= 0.7:
                            lines.append(f"- {val['pattern']} (confidence: {conf})")
        lines.append("")

    # Learned lessons (sorted by confidence, top 10)
    lessons = expertise.get("learned_lessons", [])
    high_conf = sorted(lessons, key=lambda x: x.get("confidence", 0), reverse=True)[:10]
    if high_conf:
        lines.append("### Learned Lessons")
        for lesson in high_conf:
            if lesson.get("confidence", 0) >= 0.5:
                lines.append(f"- {lesson['lesson']} (confidence: {lesson['confidence']})")
        lines.append("")

    # Common pitfalls (sorted by occurrences)
    pitfalls = expertise.get("common_pitfalls", [])
    if pitfalls:
        lines.append("### Common Pitfalls to Avoid")
        for pf in sorted(pitfalls, key=lambda x: x.get("occurrences", 0), reverse=True)[:5]:
            lines.append(f"- {pf['pitfall']} → {pf['mitigation']}")
        lines.append("")

    return "\n".join(lines)


def trim_expertise(expertise: dict, max_lines: int = MAX_EXPERTISE_LINES) -> dict:
    """Trim expertise to stay under the line limit.

    Removes lowest-confidence lessons and least-frequent pitfalls first.

    Args:
        expertise: The expertise dict.
        max_lines: Maximum allowed lines when serialized as YAML.

    Returns:
        The trimmed expertise dict.
    """
    content = yaml.dump(expertise, default_flow_style=False, sort_keys=False)
    if len(content.split("\n")) <= max_lines:
        return expertise

    # Trim lessons by confidence (remove lowest first)
    lessons = expertise.get("learned_lessons", [])
    if lessons:
        lessons.sort(key=lambda x: x.get("confidence", 0))
        while lessons:
            expertise["learned_lessons"] = lessons
            content = yaml.dump(expertise, default_flow_style=False, sort_keys=False)
            if len(content.split("\n")) <= max_lines:
                return expertise
            lessons.pop(0)  # Remove lowest confidence

    # Trim pitfalls by occurrences (remove least frequent first)
    pitfalls = expertise.get("common_pitfalls", [])
    if pitfalls:
        pitfalls.sort(key=lambda x: x.get("occurrences", 0))
        while pitfalls:
            expertise["common_pitfalls"] = pitfalls
            content = yaml.dump(expertise, default_flow_style=False, sort_keys=False)
            if len(content.split("\n")) <= max_lines:
                return expertise
            pitfalls.pop(0)

    # Trim domain knowledge keys
    domain = expertise.get("domain_knowledge", {})
    if domain:
        keys = list(domain.keys())
        while keys:
            expertise["domain_knowledge"] = {k: domain[k] for k in keys}
            content = yaml.dump(expertise, default_flow_style=False, sort_keys=False)
            if len(content.split("\n")) <= max_lines:
                return expertise
            keys.pop()  # Remove last domain category

    return expertise


def format_expertise_summary(agent_name: str) -> str:
    """Format agent expertise as an ASCII summary.

    Args:
        agent_name: The agent name.

    Returns:
        Formatted summary string.
    """
    expertise = load_agent_expertise(agent_name)
    if expertise is None:
        return f"  No expertise recorded for {agent_name}.\n"

    overview = expertise.get("overview", {})
    stats = expertise.get("performance_stats", {})
    lessons = expertise.get("learned_lessons", [])
    pitfalls = expertise.get("common_pitfalls", [])

    lines = [
        f"  Agent: {agent_name}",
        f"  ─────────────────────────────────────",
        f"  Sessions: {overview.get('total_sessions', 0)}"
        f"    Features: {overview.get('total_features', 0)}"
        f"    Success: {overview.get('success_rate', 0):.0%}",
        f"  First-pass: {stats.get('first_pass_rate', 0):.0%}"
        f"    Retries: {stats.get('total_retries', 0)}",
        f"  Lessons: {len(lessons)}    Pitfalls: {len(pitfalls)}",
        f"  ─────────────────────────────────────",
    ]

    if lessons:
        lines.append("  Top lessons:")
        for lesson in sorted(lessons, key=lambda x: x.get("confidence", 0), reverse=True)[:3]:
            lines.append(f"    • {lesson['lesson'][:60]} ({lesson.get('confidence', 0):.0%})")

    if pitfalls:
        lines.append("  Top pitfalls:")
        for pf in sorted(pitfalls, key=lambda x: x.get("occurrences", 0), reverse=True)[:3]:
            lines.append(f"    ⚠ {pf['pitfall'][:60]}")

    return "\n".join(lines) + "\n"
