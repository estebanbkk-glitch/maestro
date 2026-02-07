# Maestro

Maestro is a meta-agent that routes tasks to optimal AI tools based on cost, quality, and time constraints. Instead of picking tools for you behind a black box, Maestro shows you 2-4 options with transparent tradeoffs and lets you negotiate.

## Quick Start

```bash
pip install -e .
python -m maestro
```

Or try the guided demo:

```bash
python -m maestro --demo
```

## What It Does

You describe a task. Maestro analyzes it, generates options with real cost estimates, and lets you negotiate:

```
Maestro> Scrape 100 dive shop websites and extract pricing

  Understood: scrape 100 dive shops for pricing

  Analyzing task...

  Here's my recommendation:

  Strategy: Scrapy + Playwright fallback + DeepSeek extraction

    💰 Cost: $0.18  ✅
    ✨ Quality: 88%  ✅
    ⏱️  Time: 1m 17s  ✅

  Proceed with this approach? (yes / show options / adjust)

Maestro> under $0.10

  Here are your options:

  Option A: Budget Optimized
    Scrapy-only crawling + DeepSeek extraction
    💰 Cost: $0.03  ✅  ✨ Quality: 75%  ✅  ⏱️  Time: 84s  ✅

  Option B: Scope Reduction ⭐ Recommended
    Balanced approach but 56 sites instead of 100
    💰 Cost: $0.10  ✅  ✨ Quality: 88%  ✅  ⏱️  Time: 43s  ✅

  Option C: Balanced
    Scrapy + Playwright fallback + DeepSeek extraction
    💰 Cost: $0.18  ⚠️ $0.08 over budget  ✨ Quality: 88%  ✅

  Which option? (A/B/C/... or adjust constraints)

Maestro> B

  Starting execution...
  ✅ Complete!
    💰 Final cost: $0.09
    ✨ Quality: 93% (52/56 successful)
    ⏱️  Time: 0m 38s
```

## Supported Task Types

### Web Scraping
```
Scrape 100 dive shop websites and extract pricing
Crawl 50 restaurant sites for contact info
```

### Data Analysis
```
Analyze 500 rows of customer data for trends
Process 1000 records in the sales CSV for patterns
```

### API Integration
```
Fetch pricing from 20 hotel booking APIs
Call 10 payment endpoints to check status
```

## How It Works

Maestro balances three competing constraints — the **constraint triangle**:

```
        Quality
          /\
         /  \
        /    \
       /______\
    Cost     Time
```

You set priorities and hard limits. Maestro generates options that navigate the tradeoffs:

- **Budget option** — minimize cost, may sacrifice quality
- **Quality option** — maximize success rate, costs more
- **Speed option** — minimize time, may lower quality
- **Balanced option** — optimize all three (recommended by default)

When your constraints conflict, Maestro shows you *why* and *what you can trade*.

### Negotiation Commands

| Input | What happens |
|-------|-------------|
| `yes` / `go` | Accept the recommendation |
| `show options` | See all 4 strategies side by side |
| `under $0.50` | Set a budget constraint, regenerate options |
| `faster` | Prioritize speed |
| `better quality` | Prioritize quality |
| `at least 95%` | Set a minimum quality threshold |
| `only 50 sites` | Reduce scope |
| `A` / `B` / `C` | Pick a specific option |
| `quit` | Cancel the task |

### Preference Learning

Maestro records your choices to `~/.maestro/preferences.json`. After a few tasks, it adjusts its default recommendation based on your history. If you consistently pick Budget options for scraping tasks, it will recommend Budget first next time.

## Architecture

```
maestro/
├── models.py        # Task, Constraint, Option, Violation, ExecutionResult
├── analyzer.py      # Parse natural language → structured Task (regex + LLM)
├── generator.py     # Generate 3-4 execution strategies with cost estimates
├── validator.py     # Check options against constraints, flag violations
├── negotiator.py    # Format recommendations, parse user adjustments
├── executor.py      # Mock execution with progress simulation
├── learner.py       # Record choices, surface preferred strategies
├── cli.py           # Interactive CLI (Rich-powered, demo mode)
└── __main__.py      # Entry point with argparse

tools.yaml           # Tool definitions with real API pricing
```

### Cost Model

Costs are grounded in real API pricing (see `tools.yaml`):

| Tool | Type | Cost |
|------|------|------|
| Scrapy | Crawler | Free (local) |
| Playwright | Browser renderer | ~$0.01/page |
| httpx | HTTP client | Free |
| requests | HTTP client | Free |
| pandas / polars | Data processing | Free (local) |
| DeepSeek | LLM extraction | ~$0.0003/page |
| Claude | LLM extraction | ~$0.0038/page |

## Current Status

**v0.1.0** — proof of concept with mock execution.

- 3 task types: web scraping, data analysis, API integration
- Costs grounded in real API pricing
- Constraint negotiation with budget/quality/time/scope adjustments
- Mock execution with progress simulation and JSON output
- Preference learning from user choices
- `--demo` flag for guided walkthrough
- 87 tests passing

### Roadmap

- [ ] Real LLM integration (DeepSeek for task analysis — analyzer already wired)
- [ ] Real tool execution (Scrapy, Playwright, httpx)
- [ ] Additional task types (content generation, image processing)
- [ ] Web UI

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v

# Run the CLI
python -m maestro

# Run the guided demo
python -m maestro --demo
```

### Adding a New Task Type

See [CONTRIBUTING.md](CONTRIBUTING.md) for the step-by-step guide.

## Why Maestro?

**Not just cost optimization.** Others say "we save you money." Maestro says "we show you tradeoffs."

**Not just smart routing.** Others use a black box. Maestro gives you a transparent negotiation.

**Not just automation.** Others set-and-forget. Maestro learns your preferences and improves over time.

## License

MIT — see [LICENSE](LICENSE).

## Author

**potato, CC, water** — [esteban.bkk@gmail.com](mailto:esteban.bkk@gmail.com)
