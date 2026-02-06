"""Tests for data models."""

from maestro.models import (
    Constraint,
    ConstraintStatus,
    ExecutionResult,
    Option,
    Priority,
    Task,
    Violation,
)


def test_task_creation():
    t = Task(type="scraping", description="test", parameters={"count": 10})
    assert t.type == "scraping"
    assert t.parameters["count"] == 10


def test_constraint_defaults():
    c = Constraint()
    assert c.budget_max is None
    assert c.quality_min is None
    assert c.time_max is None
    assert c.priority == Priority.BALANCED


def test_option_defaults():
    o = Option(
        name="test", strategy="test", cost=1.0, quality=0.9,
        time_seconds=60, explanation="test", tools=["a"],
    )
    assert o.violations == []
    assert o.status == ConstraintStatus.PASS
    assert o.recommended is False


def test_violation():
    v = Violation(constraint="budget", limit=1.0, actual=1.5, delta_pct=50.0)
    assert v.delta_pct == 50.0


def test_priority_enum():
    assert Priority.COST.value == "cost"
    assert Priority.BALANCED.value == "balanced"


def test_execution_result():
    o = Option(
        name="t", strategy="t", cost=1.0, quality=0.9,
        time_seconds=60, explanation="t", tools=["a"],
    )
    r = ExecutionResult(
        option=o, actual_cost=0.95, actual_quality=0.92,
        actual_time_seconds=55, success=True,
        pages_processed=100, pages_succeeded=92, output_file="test.json",
    )
    assert r.success
    assert r.actual_cost == 0.95
