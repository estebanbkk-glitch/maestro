# Contributing to Maestro

## Development Setup

```bash
# Clone the repo
git clone https://github.com/estebansanchez/maestro.git
cd maestro

# Install with dev dependencies
pip install -e ".[dev]"

# Verify everything works
python -m pytest tests/ -v
```

## Running

```bash
# Interactive CLI
python -m maestro

# Guided demo
python -m maestro --demo

# Or via console_scripts entry point (after install)
maestro
```

## Running Tests

```bash
# All tests
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=maestro --cov-report=term-missing

# Single file
python -m pytest tests/test_analyzer.py -v
```

## Project Structure

```
maestro/
├── models.py        # Data structures (Task, Option, Constraint, etc.)
├── analyzer.py      # Parse natural language → structured Task
├── generator.py     # Generate 3-4 execution strategies with cost estimates
├── validator.py     # Check options against constraints
├── negotiator.py    # Format options for display, parse user adjustments
├── executor.py      # Execute tasks (mock for now)
├── learner.py       # Record choices for preference learning
├── cli.py           # Interactive CLI state machine
└── __main__.py      # Entry point

tools.yaml           # Tool definitions with pricing
tests/               # Test suite
examples/            # Example sessions
```

## Adding a New Task Type

Adding a task type touches 5 files. Here's the pattern, using "api" as an example:

### 1. `tools.yaml` — add tool definitions

```yaml
httpx:
  name: httpx
  type: http_client
  cost_per_request: 0.0
  success_rate: 0.95
  speed_requests_per_second: 10.0
  quality: 0.90
  description: "Async HTTP client."
```

### 2. `maestro/analyzer.py` — add detection

Add regex patterns for your task type (triggers, count patterns, source/target patterns).
Add an `_analyze_as_<type>()` method to `RegexTaskAnalyzer`.
Update the `analyze()` method with detection logic.
Update the LLM `_SYSTEM_PROMPT` to classify the new type.

### 3. `maestro/generator.py` — add option generation

Add a `_generate_<type>_options()` method that returns 4 `Option` objects:
- Budget, Balanced (recommended), Quality, Speed

Add `_generate_<type>_scope_reduction()` for budget-constrained scenarios.
Update the `generate()` method to dispatch to your new generator.

### 4. `maestro/executor.py` — add execution

Add `_build_<type>_phases()` for progress display.
Add `_build_<type>_results()` for fake output data.
Update `_build_phases()` dispatch and the progress label.

### 5. `maestro/cli.py` — update messages

Update the welcome message, error hints, "understood" display, and scope hint.

### 6. Tests

Add tests in `test_analyzer.py` (detection, count extraction, source extraction).
Add tests in `test_generator.py` (4 options, budget cheapest, cost scaling, scope reduction).
Add an integration test in `test_negotiation_flow.py`.

## Code Style

- Type hints on all function signatures
- Docstrings on all public methods
- Functions under 50 lines
- Use `dataclasses` for models
- Use `rich` for CLI output

## Pull Requests

1. Create a feature branch from `master`
2. Make your changes
3. Ensure all tests pass: `python -m pytest tests/ -v`
4. Write tests for new functionality
5. Keep commits focused — one logical change per commit
6. Open a PR with a clear description of what and why

## Design Principles

- **Negotiation is the product** — everything supports the conversation
- **Explicit over implicit** — show tradeoffs, don't hide them
- **Simple over clever** — three similar lines > premature abstraction
- **Working over perfect** — mock it first, implement later
- **Tested over documented** — but document too
