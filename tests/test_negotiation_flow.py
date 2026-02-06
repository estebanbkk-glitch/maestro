"""Integration tests for the full negotiation flow."""

from maestro.analyzer import TaskAnalyzer
from maestro.generator import OptionGenerator
from maestro.models import Constraint
from maestro.negotiator import Negotiator, UserIntent
from maestro.validator import ConstraintValidator


def test_full_flow_scraping():
    """Simulate: analyze task → generate options → negotiate → pick."""
    analyzer = TaskAnalyzer()
    generator = OptionGenerator()
    validator = ConstraintValidator()
    negotiator = Negotiator()

    # Step 1: Parse task
    task = analyzer.analyze("Scrape 100 dive shop websites and extract pricing")
    assert task is not None
    assert task.parameters["count"] == 100

    # Step 2: Generate initial options
    options = generator.generate(task)
    assert len(options) == 4

    # Step 3: User says "under $0.10" (balanced is ~$0.18 so this triggers scope reduction)
    parsed = negotiator.parse_input("can we do it for under $0.10?", len(options))
    assert parsed.intent == UserIntent.ADJUST_BUDGET
    assert parsed.value == 0.10

    # Step 4: Build constraint and regenerate
    constraint = negotiator.build_constraint_from_adjustment(parsed)
    assert constraint.budget_max == 0.10

    options = generator.generate(task, constraint)
    validator.validate(options, constraint)

    # Should have scope reduction option
    scope = [o for o in options if o.name == "Scope Reduction"]
    assert len(scope) == 1
    assert scope[0].cost <= 0.10

    # Step 5: User picks option B
    parsed = negotiator.parse_input("B", len(options))
    assert parsed.intent == UserIntent.ACCEPT
    assert parsed.chosen_index == 1


def test_negotiation_cheaper():
    negotiator = Negotiator()
    parsed = negotiator.parse_input("cheaper")
    assert parsed.intent == UserIntent.ADJUST_BUDGET


def test_negotiation_faster():
    negotiator = Negotiator()
    parsed = negotiator.parse_input("faster")
    assert parsed.intent == UserIntent.ADJUST_TIME


def test_negotiation_quality():
    negotiator = Negotiator()
    parsed = negotiator.parse_input("at least 95%")
    assert parsed.intent == UserIntent.ADJUST_QUALITY
    assert parsed.value == 0.95


def test_negotiation_scope():
    negotiator = Negotiator()
    parsed = negotiator.parse_input("only 50 sites")
    assert parsed.intent == UserIntent.ADJUST_SCOPE
    assert parsed.value == 50


def test_negotiation_quit():
    negotiator = Negotiator()
    for word in ["quit", "exit", "cancel", "no"]:
        parsed = negotiator.parse_input(word)
        assert parsed.intent == UserIntent.QUIT, f"Failed for: {word}"


def test_negotiation_accept():
    negotiator = Negotiator()
    for word in ["yes", "go", "proceed"]:
        parsed = negotiator.parse_input(word)
        assert parsed.intent == UserIntent.ACCEPT, f"Failed for: {word}"


def test_option_formatting():
    """Ensure formatting doesn't crash."""
    generator = OptionGenerator()
    negotiator = Negotiator()

    from maestro.models import Task
    task = Task(type="scraping", description="test", parameters={"count": 50, "domain": "hotels"})
    options = generator.generate(task)

    # Should not raise
    output = negotiator.format_recommendation(options)
    assert "Cost" in output
    assert "$" in output

    output = negotiator.format_options(options)
    assert "Option A" in output
    assert "Option B" in output


def test_dollar_amount_only():
    negotiator = Negotiator()
    parsed = negotiator.parse_input("$5")
    assert parsed.intent == UserIntent.ADJUST_BUDGET
    assert parsed.value == 5.0


def test_under_minutes():
    negotiator = Negotiator()
    parsed = negotiator.parse_input("under 5 minutes")
    assert parsed.intent == UserIntent.ADJUST_TIME
    assert parsed.value == 300  # 5 minutes in seconds
