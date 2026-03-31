"""Data models shared across RAPIDS core modules."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScopeResult:
    """Result of scope classification."""

    tier: int
    phases: list[str]
    reasoning: str = ""


@dataclass
class ModelConfig:
    """Resolved model configuration for a given context."""

    model: str
    effort: str
    max_turns: int = 100


@dataclass
class ValidationResult:
    """Result of artifact or plugin validation."""

    valid: bool
    error: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class CostEntry:
    """A single cost log entry."""

    ts: str
    phase: str
    feature: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class CostSummary:
    """Aggregated cost summary."""

    total_cost: float
    total_input_tokens: int
    total_output_tokens: int
    by_phase: dict[str, float] = field(default_factory=dict)
    by_feature: dict[str, float] = field(default_factory=dict)
    by_model: dict[str, float] = field(default_factory=dict)
    entry_count: int = 0
