"""Data models for Maestro."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Priority(Enum):
    """User's optimization priority."""
    COST = "cost"
    QUALITY = "quality"
    TIME = "time"
    BALANCED = "balanced"


class ConstraintStatus(Enum):
    """Result of validating an option against constraints."""
    PASS = "pass"
    PARTIAL = "partial"   # <10% violation
    FAIL = "fail"         # >10% violation


@dataclass
class Task:
    """A parsed user request."""
    type: str                         # "scraping"
    description: str                  # Original user input
    parameters: dict[str, object]     # {"count": 100, "domain": "dive shops", "target": "pricing"}


@dataclass
class Constraint:
    """User-defined limits on cost, quality, and time."""
    budget_max: float | None = None       # USD hard limit
    quality_min: float | None = None      # 0.0-1.0
    time_max: int | None = None           # Seconds
    priority: Priority = Priority.BALANCED


@dataclass
class Violation:
    """A single constraint violation."""
    constraint: str     # "budget", "quality", "time"
    limit: float
    actual: float
    delta_pct: float    # How far over/under (positive = bad)


@dataclass
class Option:
    """One execution strategy with estimated cost/quality/time."""
    name: str               # "Budget Optimized"
    strategy: str           # "Scrapy-only with DeepSeek extraction"
    cost: float             # USD
    quality: float          # 0.0-1.0
    time_seconds: int       # Estimated seconds
    explanation: str        # Why this approach
    tools: list[str]        # ["scrapy", "deepseek"]
    violations: list[Violation] = field(default_factory=list)
    status: ConstraintStatus = ConstraintStatus.PASS
    recommended: bool = False


@dataclass
class ExecutionResult:
    """Outcome of executing an option (mocked for MVP)."""
    option: Option
    actual_cost: float
    actual_quality: float
    actual_time_seconds: int
    success: bool
    pages_processed: int
    pages_succeeded: int
    output_file: str
