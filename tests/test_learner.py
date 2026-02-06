"""Tests for PreferenceLearner and its influence on recommendations."""

import json
from pathlib import Path

import pytest

from maestro.generator import OptionGenerator
from maestro.learner import PreferenceLearner
from maestro.models import Constraint, ExecutionResult, Option, Task


@pytest.fixture()
def prefs_file(tmp_path, monkeypatch):
    """Redirect preference storage to a temp directory."""
    prefs_dir = tmp_path / ".maestro"
    prefs_file = prefs_dir / "preferences.json"
    monkeypatch.setattr("maestro.learner._PREFS_DIR", prefs_dir)
    monkeypatch.setattr("maestro.learner._PREFS_FILE", prefs_file)
    return prefs_file


def _make_task(count: int = 100) -> Task:
    return Task(
        type="scraping",
        description=f"Scrape {count} sites",
        parameters={"count": count, "domain": "dive shops", "target": "pricing"},
    )


def _make_option(name: str = "Budget Optimized") -> Option:
    return Option(
        name=name,
        strategy="test",
        cost=0.10,
        quality=0.85,
        time_seconds=60,
        explanation="test",
        tools=["scrapy"],
    )


# --- get_preferred_strategy ---


def test_no_history_returns_none(prefs_file):
    learner = PreferenceLearner()
    assert learner.get_preferred_strategy("scraping") is None


def test_insufficient_history_returns_none(prefs_file):
    """One choice isn't enough to form a preference."""
    learner = PreferenceLearner()
    learner.record_choice(_make_task(), [_make_option()], _make_option("Budget Optimized"), None)
    assert learner.get_preferred_strategy("scraping") is None


def test_clear_preference_returns_name(prefs_file):
    """Two matching choices should establish a preference."""
    learner = PreferenceLearner()
    task = _make_task()
    opt = _make_option("Budget Optimized")
    learner.record_choice(task, [opt], opt, None)
    learner.record_choice(task, [opt], opt, None)
    assert learner.get_preferred_strategy("scraping") == "Budget Optimized"


def test_mixed_choices_no_majority(prefs_file):
    """No option has >50% — should return None."""
    learner = PreferenceLearner()
    task = _make_task()
    for name in ["Budget Optimized", "Balanced", "Quality Focused", "Speed Optimized"]:
        learner.record_choice(task, [_make_option(name)], _make_option(name), None)
    assert learner.get_preferred_strategy("scraping") is None


def test_preference_scoped_to_task_type(prefs_file):
    """Preferences from 'analysis' shouldn't affect 'scraping'."""
    learner = PreferenceLearner()
    analysis_task = Task(type="analysis", description="test", parameters={})
    opt = _make_option("Quality Focused")
    learner.record_choice(analysis_task, [opt], opt, None)
    learner.record_choice(analysis_task, [opt], opt, None)
    # Analysis has a preference, scraping does not
    assert learner.get_preferred_strategy("analysis") == "Quality Focused"
    assert learner.get_preferred_strategy("scraping") is None


# --- Generator preferred_strategy ---


def test_generator_default_recommends_balanced():
    gen = OptionGenerator()
    options = gen.generate(_make_task())
    recommended = [o for o in options if o.recommended]
    assert len(recommended) == 1
    assert recommended[0].name == "Balanced"


def test_generator_shifts_recommendation():
    gen = OptionGenerator()
    options = gen.generate(_make_task(), preferred_strategy="Budget Optimized")
    recommended = [o for o in options if o.recommended]
    assert len(recommended) == 1
    assert recommended[0].name == "Budget Optimized"


def test_generator_ignores_unknown_preference():
    """If preferred_strategy doesn't match any option name, keep Balanced."""
    gen = OptionGenerator()
    options = gen.generate(_make_task(), preferred_strategy="Nonexistent")
    recommended = [o for o in options if o.recommended]
    assert len(recommended) == 1
    assert recommended[0].name == "Balanced"


def test_generator_preference_with_constraint():
    """Preference should work alongside budget constraints."""
    gen = OptionGenerator()
    constraint = Constraint(budget_max=0.10)
    options = gen.generate(_make_task(), constraint, preferred_strategy="Budget Optimized")
    recommended = [o for o in options if o.recommended]
    assert len(recommended) == 1
    assert recommended[0].name == "Budget Optimized"
    # Scope reduction should still be generated
    assert any(o.name == "Scope Reduction" for o in options)


# --- Integration: learner → generator ---


def test_learner_influences_generator(prefs_file):
    """Full cycle: record budget choices, then preference shifts recommendation."""
    learner = PreferenceLearner()
    gen = OptionGenerator()
    task = _make_task()

    # Record two budget choices
    opt = _make_option("Budget Optimized")
    learner.record_choice(task, [opt], opt, None)
    learner.record_choice(task, [opt], opt, None)

    # Learner should now prefer budget
    preferred = learner.get_preferred_strategy("scraping")
    assert preferred == "Budget Optimized"

    # Generator should shift recommendation
    options = gen.generate(task, preferred_strategy=preferred)
    recommended = [o for o in options if o.recommended]
    assert recommended[0].name == "Budget Optimized"
