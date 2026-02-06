# Maestro

Maestro is a meta-agent that routes tasks to optimal AI tools based on cost, quality, and time constraints. Instead of picking tools for you behind a black box, Maestro shows you 2-4 options with transparent tradeoffs and lets you negotiate.

## Quick Start

```bash
pip install -e .
python -m maestro
```

## Example Session

```
╭──────────────────────────────────╮
│          Maestro                 │
│ Intelligent AI Tool Orchestration│
╰──────────────────────────────────╯
  Describe a scraping task, and I'll show you the best approach.

Maestro> Scrape 100 dive shop websites and extract pricing

  Analyzing task...

📊 Recommendation: Hybrid Scrapy+Playwright

  Strategy: Use Scrapy for static pages (~85%), Playwright for JS-heavy
  sites (~15%), DeepSeek for data extraction.

  💰 Cost:    $0.53
  ✨ Quality: 92%
  ⏱️  Time:    12 min

  Proceed? (yes / adjust / show options)

Maestro> Can we do it for under $0.30?

  To meet your $0.30 budget, here are your options:

  Option A: Budget Optimized
    Scrapy-only, skip JS-heavy sites
    💰 $0.03 ✅  ✨ 75% ✅  ⏱️ 8 min ✅

  Option B: Scope Reduction ⭐ Recommended
    Full hybrid approach, 56 sites
    💰 $0.30 ✅  ✨ 92% ✅  ⏱️ 7 min ✅

  Option C: Balanced
    Scrapy + selective Playwright
    💰 $0.33 ⚠️ 10% over  ✨ 88% ✅  ⏱️ 10 min ✅

Maestro> B

  ✅ Confirmed: Scope Reduction
  Processing 56 dive shop sites...

  ⏳ Executing...
  Progress: ████████████████████ 56/56
  Running cost: $0.28

  ✅ Complete!
    💰 Final cost: $0.28
    ✨ Quality:    93% (52/56 successful)
    ⏱️  Time:       6m 42s

    Results saved to: output/maestro_result_20260206_143022.json
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
- **Quality option** — maximize success rate, may cost more
- **Speed option** — minimize time, may lower quality
- **Balanced option** — optimize all three (recommended by default)

When your constraints conflict, Maestro shows you *why* and *what you can trade*.

## Architecture

```
maestro/
├── models.py        # Task, Constraint, Option, Violation, ExecutionResult
├── analyzer.py      # Parse natural language → structured Task
├── generator.py     # Generate 3-4 execution strategies with cost estimates
├── validator.py     # Check options against constraints, flag violations
├── negotiator.py    # Format recommendations, parse user adjustments
├── executor.py      # Mock execution with progress simulation
├── learner.py       # Record choices for future recommendations
└── cli.py           # Interactive CLI (Rich-powered)

tools.yaml           # Tool definitions with real API pricing
```

## Current Status

**MVP** — proof of concept with mock execution.

- Single task type: web scraping
- Costs grounded in real API pricing (see `tools.yaml`)
- Mock execution (simulates progress, writes JSON results)
- 39 tests passing

### What's next

- Real LLM integration (replace regex analyzer with API call)
- Wire up preference learning to influence recommendations
- Additional task types (data analysis, content generation)
- Real tool execution

## Development

```bash
pip install -e ".[dev]"
python -m pytest tests/
```

## License

MIT
