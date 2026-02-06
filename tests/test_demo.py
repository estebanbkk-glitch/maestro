"""Tests for demo mode."""

from maestro.analyzer import TaskAnalyzer
from maestro.cli import MaestroCLI


def test_demo_scenarios_defined():
    """demo=True creates 3 scenarios."""
    cli = MaestroCLI(demo=True)
    assert len(cli.demo_scenarios) == 3
    titles = [s["title"] for s in cli.demo_scenarios]
    assert "Web Scraping" in titles
    assert "Data Analysis" in titles
    assert "API Integration" in titles


def test_non_demo_has_no_scenarios():
    """demo=False has empty scenario list."""
    cli = MaestroCLI(demo=False)
    assert cli.demo_scenarios == []


def test_demo_suggestions_are_parseable():
    """All task suggestions in demo scenarios should be recognized by the analyzer."""
    analyzer = TaskAnalyzer()
    scenarios = MaestroCLI._build_demo_scenarios()
    for scenario in scenarios:
        task = analyzer.analyze(scenario["task_suggestion"])
        assert task is not None, f"Analyzer failed to parse: {scenario['task_suggestion']}"
        assert task.type in ("scraping", "analysis", "api"), (
            f"Unexpected type {task.type} for: {scenario['task_suggestion']}"
        )
