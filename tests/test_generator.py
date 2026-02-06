"""Tests for OptionGenerator."""

from maestro.generator import OptionGenerator
from maestro.models import Constraint, Task


def _make_task(count: int = 100) -> Task:
    return Task(
        type="scraping",
        description=f"Scrape {count} sites",
        parameters={"count": count, "domain": "dive shops", "target": "pricing"},
    )


def test_generates_four_options():
    gen = OptionGenerator()
    options = gen.generate(_make_task())
    assert len(options) == 4


def test_one_option_is_recommended():
    gen = OptionGenerator()
    options = gen.generate(_make_task())
    recommended = [o for o in options if o.recommended]
    assert len(recommended) == 1
    assert recommended[0].name == "Balanced"


def test_budget_option_is_cheapest():
    gen = OptionGenerator()
    options = gen.generate(_make_task())
    budget = next(o for o in options if o.name == "Budget Optimized")
    for other in options:
        if other is not budget:
            assert budget.cost <= other.cost


def test_quality_option_has_highest_quality():
    gen = OptionGenerator()
    options = gen.generate(_make_task())
    quality = next(o for o in options if o.name == "Quality Focused")
    for other in options:
        if other is not quality:
            assert quality.quality >= other.quality


def test_speed_option_is_fastest():
    gen = OptionGenerator()
    options = gen.generate(_make_task())
    speed = next(o for o in options if o.name == "Speed Optimized")
    for other in options:
        if other is not speed:
            assert speed.time_seconds <= other.time_seconds


def test_costs_scale_with_count():
    gen = OptionGenerator()
    small = gen.generate(_make_task(10))
    large = gen.generate(_make_task(100))
    # Balanced option cost should scale ~linearly
    small_balanced = next(o for o in small if o.name == "Balanced")
    large_balanced = next(o for o in large if o.name == "Balanced")
    assert large_balanced.cost > small_balanced.cost * 5  # ~10x, with some tolerance


def test_scope_reduction_generated_when_budget_tight():
    gen = OptionGenerator()
    # Balanced cost for 100 pages is ~$0.18, so $0.10 is tight enough
    constraint = Constraint(budget_max=0.10)
    options = gen.generate(_make_task(100), constraint)
    scope_options = [o for o in options if o.name == "Scope Reduction"]
    assert len(scope_options) == 1
    assert scope_options[0].cost <= 0.10


def test_no_scope_reduction_when_budget_sufficient():
    gen = OptionGenerator()
    constraint = Constraint(budget_max=100.0)
    options = gen.generate(_make_task(10), constraint)
    scope_options = [o for o in options if o.name == "Scope Reduction"]
    assert len(scope_options) == 0


def test_all_options_have_tools():
    gen = OptionGenerator()
    options = gen.generate(_make_task())
    for option in options:
        assert len(option.tools) >= 1
        assert all(isinstance(t, str) for t in option.tools)


def test_costs_are_realistic():
    """100 pages should cost somewhere between $0.10 and $10."""
    gen = OptionGenerator()
    options = gen.generate(_make_task(100))
    for option in options:
        assert 0.01 < option.cost < 10.0, f"{option.name} cost {option.cost} is unrealistic"
