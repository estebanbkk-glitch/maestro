"""Tests for ConstraintValidator."""

from maestro.models import Constraint, ConstraintStatus, Option
from maestro.validator import ConstraintValidator


def _make_option(cost: float = 1.0, quality: float = 0.9, time: int = 60) -> Option:
    return Option(
        name="Test",
        strategy="test",
        cost=cost,
        quality=quality,
        time_seconds=time,
        explanation="test",
        tools=["test"],
    )


def test_no_constraints_all_pass():
    v = ConstraintValidator()
    options = [_make_option()]
    v.validate(options, Constraint())
    assert options[0].status == ConstraintStatus.PASS
    assert len(options[0].violations) == 0


def test_budget_violation():
    v = ConstraintValidator()
    options = [_make_option(cost=2.0)]
    v.validate(options, Constraint(budget_max=1.0))
    assert options[0].status == ConstraintStatus.FAIL
    assert len(options[0].violations) == 1
    assert options[0].violations[0].constraint == "budget"
    assert options[0].violations[0].delta_pct == 100.0  # 2x over


def test_quality_violation():
    v = ConstraintValidator()
    options = [_make_option(quality=0.7)]
    v.validate(options, Constraint(quality_min=0.9))
    assert len(options[0].violations) == 1
    assert options[0].violations[0].constraint == "quality"


def test_time_violation():
    v = ConstraintValidator()
    options = [_make_option(time=120)]
    v.validate(options, Constraint(time_max=60))
    assert len(options[0].violations) == 1
    assert options[0].violations[0].constraint == "time"


def test_partial_status_for_small_violations():
    v = ConstraintValidator()
    # 5% over budget — should be PARTIAL
    options = [_make_option(cost=1.05)]
    v.validate(options, Constraint(budget_max=1.0))
    assert options[0].status == ConstraintStatus.PARTIAL


def test_multiple_violations():
    v = ConstraintValidator()
    options = [_make_option(cost=5.0, quality=0.5)]
    v.validate(options, Constraint(budget_max=1.0, quality_min=0.9))
    assert len(options[0].violations) == 2


def test_passing_option_has_no_violations():
    v = ConstraintValidator()
    options = [_make_option(cost=0.50, quality=0.95, time=30)]
    v.validate(options, Constraint(budget_max=1.0, quality_min=0.9, time_max=60))
    assert options[0].status == ConstraintStatus.PASS
    assert len(options[0].violations) == 0
