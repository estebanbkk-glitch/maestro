# Maestro Project Context
**Last Updated:** February 5, 2026  
**Project:** Maestro - Intelligent AI Tool Orchestration with Constraint Negotiation  
**Status:** MVP Development Phase

---

## PROJECT OVERVIEW

**What is Maestro?**

Maestro is a meta-agent that routes tasks to optimal AI tools (LLM APIs, agents, automation tools) based on cost, quality, and time constraints. The key innovation is **conversational constraint negotiation** - Maestro doesn't just pick tools, it negotiates tradeoffs with users transparently.

**Core workflow:**
1. User sends task → Maestro analyzes and recommends approach
2. User can negotiate ("Can we do $5?") → Maestro shows 2-4 options with tradeoffs
3. User picks option → Maestro executes
4. System learns from user choices → Gets better over time

**Why this matters:**

Instead of "AI picks for me" (black box, frustrating), users get "AI shows me my options" (transparent, empowering). This is the core differentiator.

---

## THE KEY INSIGHT

**The constraint negotiation IS the product.**

Everything else (routing logic, cost calculations, tool selection) supports the negotiation conversation. If the conversation feels natural and transparent → we've won.

**Priority order:**
1. Negotiation UX (must feel right)
2. Constraint validation (accurate tradeoffs)
3. Option generation (2-4 clear choices)
4. Cost/quality/time estimation (can be rough initially)
5. Actual execution (can be mocked for MVP)

---

## CURRENT PHASE: MVP

**Scope:** Single use case (web scraping), mock execution, focus on negotiation flow

**What to build:**
- ✅ Data models (Task, Option, Constraint, ExecutionResult)
- ✅ OptionGenerator (hardcoded scraping logic)
- ✅ ConstraintNegotiator (conversation formatting)
- ✅ Simple CLI with Rich library
- ✅ Mock executor (simulate with progress)
- ✅ Basic tests

**What NOT to build yet:**
- ❌ Real LLM API integration (use mock responses)
- ❌ Real tool execution (simulate only)
- ❌ Multiple use cases (just scraping)
- ❌ Database (in-memory dict is fine)
- ❌ Web UI (CLI only)
- ❌ Advanced learning (just record choices)

---

## ARCHITECTURE DECISIONS

### The Constraint Triangle

```
           Quality
             /\
            /  \
           /    \
          /      \
         /        \
        /          \
       /____________\
    Cost          Time
```

Users set priorities (cost|quality|time|balanced). Maestro evaluates all options against constraints and shows tradeoffs when conflicts arise.

### Core Components

**1. ConversationalNegotiator**
- Presents initial recommendations
- Handles constraint adjustments
- Generates 2-4 alternative options
- Explains tradeoffs clearly

**2. TaskAnalyzer**
- Parses user input
- Extracts parameters (count, domain, etc.)
- Returns structured Task object

**3. OptionGenerator**
- Generates 3-4 execution strategies
- Calculates cost/quality/time estimates
- Always includes: budget option, quality option, balanced option

**4. ConstraintValidator**
- Checks if options meet constraints
- Returns: 'pass', 'partial', or 'fail'
- Calculates violation percentages

**5. PreferenceLearner**
- Records user choices
- Identifies patterns (user prefers X for Y tasks)
- Improves future recommendations

**6. SimpleExecutor**
- Mock for MVP (just simulate with sleep)
- Real implementation comes later

### Data Models

```python
@dataclass
class Task:
    type: str                    # 'scraping', 'analysis', etc.
    description: str             # Natural language
    parameters: Dict[str, Any]   # Extracted params
    
@dataclass
class Constraint:
    budget_max: Optional[float] = None      # Hard limit
    quality_min: Optional[float] = None     # 0.0 - 1.0
    time_max: Optional[int] = None          # seconds
    priority: str = "balanced"              # cost|quality|time|balanced

@dataclass
class Option:
    strategy: str                # "Hybrid Scrapy+Playwright"
    cost: float                  # USD
    quality: float               # 0.0 - 1.0 (success rate)
    time: int                    # seconds
    explanation: str             # Why this approach?
    tools: List[str]             # ["scrapy", "playwright", "deepseek"]
    violations: List[Dict] = []  # Constraint violations

@dataclass
class ExecutionResult:
    option: Option
    actual_cost: float
    actual_quality: float
    actual_time: int
    success: bool
    details: Dict[str, Any]
```

---

## DESIGN PATTERNS

### Option Generation Strategy

Always generate 3-4 options representing different tradeoffs:

1. **Budget option:** Minimize cost (may sacrifice quality/time)
2. **Quality option:** Maximize quality (may cost more/take longer)
3. **Speed option:** Minimize time (may cost more/lower quality)
4. **Balanced option:** Optimize all three (RECOMMENDED)

If user provides constraint, filter/adjust options accordingly.

### Natural Language Presentation

Use emojis and clear formatting:
```
💰 Cost: $X.XX [✓ within budget | ⚠️ $X.XX over]
✨ Quality: XX% [✓ meets minimum | ⚠️ X% below]
⏱️  Time: XX min [✓ on time | ⚠️ XX min over]
```

### Constraint Validation

```python
def validate(option, constraints):
    violations = []
    
    # Check each constraint
    if constraints.budget_max and option.cost > constraints.budget_max:
        delta_pct = (option.cost / constraints.budget_max - 1) * 100
        violations.append({'type': 'budget', 'delta_pct': delta_pct})
    
    # Determine status
    if not violations:
        return 'pass', []
    elif all(v['delta_pct'] < 10 for v in violations):
        return 'partial', violations  # Minor violations
    else:
        return 'fail', violations  # Major violations
```

### Learning Pattern

```python
def record_choice(task, options_shown, user_choice):
    """Track what user picked when constraints conflicted"""
    
    # User accepted budget overrun but not quality drop
    if 'budget' in user_choice.violations and 'quality' not in user_choice.violations:
        patterns['quality_over_cost'] += 1
    
    # Build preference profile
    preferences[task.type] = {
        'typically_chooses': analyze_pattern(),
        'budget_flexibility': calculate_flexibility('budget'),
        'quality_threshold': calculate_threshold('quality')
    }
```

---

## EXAMPLE INTERACTION (TARGET UX)

```
Maestro> Hello! What task can I help with?

User> Scrape 100 dive shop websites and extract pricing

Maestro> Analyzing task...

📊 Here's my recommendation:

Strategy: Hybrid approach
  • Try Scrapy first (fast, free, works for ~85% of sites)
  • Fall back to Playwright for JavaScript-heavy sites (~15%)
  • Use DeepSeek for data extraction (cheap, good at structured data)

Estimated results:
  💰 Cost: $1.35
  ✨ Quality: 92% (estimated successful extractions)
  ⏱️  Time: 12 minutes

Proceed with this approach? (yes/no/adjust)

User> Can we do it for under $1?

Maestro> To meet $1 budget, here are your options:

Option A: Budget Optimized
  • Scrapy only (no Playwright fallback)
  • DeepSeek for extraction
  💰 Cost: $0.70 ✓
  ✨ Quality: 85% ⚠️ (lower - JS sites will fail)
  ⏱️  Time: 8 minutes ✓

Option B: Scope Reduction
  • Same hybrid approach
  • But only 70 websites instead of 100
  💰 Cost: $0.95 ✓
  ✨ Quality: 92% ✓
  ⏱️  Time: 8 minutes ✓

Option C: Original (Recommended)
  • Full hybrid approach, all 100 websites
  💰 Cost: $1.35 ⚠️ ($0.35 over budget)
  ✨ Quality: 92% ✓
  ⏱️  Time: 12 minutes ✓

Which option? (A/B/C)

User> B

Maestro> ✓ Confirmed: Scope reduction approach
  Processing 70 websites with hybrid strategy...

[Mock execution with progress]

⏳ Starting execution...
   Progress: 23/70 sites processed...
   Running cost: $0.35... $0.58... $0.82...

✓ Complete!
   💰 Final cost: $0.92
   ✨ Quality: 94% (66/70 successful)
   ⏱️  Time: 7m 45s

Results saved to: results.json

📚 Learning: User accepts scope reduction to meet budget
   Next similar task: Will offer scope options first
```

---

## CODING GUIDELINES

**Style:**
- Type hints everywhere
- Docstrings for all public methods
- Use dataclasses for models
- Rich library for CLI output
- Functions < 50 lines

**Principles:**
- Explicit over implicit
- Simple over clever
- Working over perfect
- Tested over documented (but document too)

**Testing:**
- Unit tests for each component
- Integration test for full workflow
- Test conversation flow thoroughly

**File structure:**
```
maestro/
├── __init__.py
├── models.py           # Data structures
├── analyzer.py         # TaskAnalyzer
├── generator.py        # OptionGenerator
├── negotiator.py       # ConversationalNegotiator
├── validator.py        # ConstraintValidator
├── learner.py          # PreferenceLearner
├── executor.py         # SimpleExecutor (mock)
├── config.py           # Load YAML configs
└── main.py             # CLI entry point

tests/
├── test_models.py
├── test_generator.py
├── test_negotiator.py
├── test_validator.py
└── test_integration.py

tools.yaml              # Tool definitions and pricing
examples/
└── example_session.txt # Sample conversations
```

---

## TECHNICAL CONSTRAINTS

**Environment:**
- Python 3.11+
- Dependencies: Rich, PyYAML, dataclasses
- No database (use dict/pickle for now)
- No external APIs yet (mock responses)

**Performance:**
- Option generation: < 100ms
- Constraint validation: < 10ms
- CLI response: < 200ms (feels instant)

**Quality:**
- All public methods have docstrings
- Test coverage > 80%
- Type hints everywhere
- No warnings from mypy/pylint

---

## WHAT MAKES THIS UNIQUE

**Not just cost optimization:**
- Others: "We save you money" (defensive pitch)
- Maestro: "We show you tradeoffs" (decision support)

**Not just smart routing:**
- Others: Black box picks tool
- Maestro: Transparent negotiation with user

**Not just automation:**
- Others: Set it and forget it
- Maestro: Learn preferences, improve over time

**The moat is:**
1. Conversational UX (hard to copy)
2. Learned preferences (network effect)
3. Transparent decision-making (trust)

---

## REFERENCE DOCUMENTS

In this directory:
- `claude-code-prompt.md` - Detailed build instructions
- `meta-agent-concept-manifest.md` - Full architectural vision
- `maestro-constraint-system-update.md` - Constraint negotiation details
- `maestro-commercial-viability.md` - Market analysis & strategy
- `maestro-open-source-costs.md` - Infrastructure costs breakdown
- `setup-instructions.md` - How to start building

**Read these for more context, but this file has enough to start coding.**

---

## CURRENT PRIORITIES

**For this session:**
1. Set up project structure ✓
2. Define data models (models.py)
3. Implement OptionGenerator with hardcoded scraping logic
4. Implement ConstraintNegotiator for formatting
5. Create CLI with Rich
6. Mock executor with progress simulation
7. Write tests

**Don't do yet:**
- LLM integration
- Real tool execution  
- Multiple use cases
- Advanced learning
- Database setup

**Keep it simple. Prove the core concept.**

---

## QUESTIONS TO ANSWER WHILE CODING

**Q: How many options to show?**  
A: Always 3-4, never more (choice paralysis)

**Q: How to calculate cost/quality/time?**  
A: Start with hardcoded formulas, refine later

**Q: What if no option meets constraints?**  
A: Always show closest option + explain tradeoff

**Q: How to present violations?**  
A: Use ⚠️ emoji and "X% over/under limit"

**Q: User says "yes" to recommendation?**  
A: Just execute, no more negotiation

---

## SUCCESS CRITERIA

**You've succeeded if:**
1. ✅ CLI runs and conversation flows naturally
2. ✅ Can negotiate constraints ("Can we do $5?")
3. ✅ Shows 2-4 clear options with tradeoffs
4. ✅ Cost/quality/time displayed clearly
5. ✅ Mock execution runs with progress
6. ✅ Code is clean, tested, typed
7. ✅ I understand how to extend it

**Time box:** 3-4 hours of coding

---

## WHEN YOU'RE STUCK

**Ask yourself:**
- Does this make the negotiation clearer?
- Would a user understand this tradeoff?
- Is this simpler than alternatives?

**Refer to:**
- The example interaction above (target UX)
- The constraint triangle (core concept)
- "Negotiation IS the product" (key insight)

**Remember:**
- Mock it first, implement later
- Working > Perfect
- Conversation flow > Technical elegance

---

## PROJECT PHILOSOPHY

**Build for yourself first:**
- You need this for Hotelingo (intent recognition costs)
- You need this for Dive Directory (scraping costs)
- If it doesn't save YOU money, won't save others

**Open source by default:**
- Pure GitHub model (users self-host)
- Your cost: $0/year
- Revenue: Consulting, then maybe cloud later

**Iterate based on feedback:**
- MVP proves concept
- Community shows what's needed
- Product emerges from real usage

**Stay lean:**
- No infrastructure costs
- No complex dependencies
- No premature optimization

---

## IMPORTANT NOTES

**Model recommendation:**
- Use Sonnet 4.5 (not Opus)
- Specs are clear, no ambiguity needed
- 80% cheaper, more iterations
- Switch to Opus only if stuck

**Cost tracking:**
- MVP should cost ~$20-30 in API calls
- If exceeding $50, something's wrong
- Most work is local (no APIs needed)

**Time estimate:**
- This session: 3-4 hours
- Full MVP: 40-60 hours total
- Don't rush, focus on quality

---

## NEXT STEPS AFTER MVP

**Phase 2:**
- Add real LLM integration (DeepSeek for task analysis)
- Load tool configs from YAML
- Calculate costs dynamically
- Save preferences to JSON

**Phase 3:**
- Real tool execution (call Scrapy, Playwright)
- Progress tracking
- Error handling
- More use cases

**Phase 4:**
- Open source release
- Documentation
- Examples
- Community building

---

## CONTACT & COLLABORATION

**Maintainer:** Esteban Sanchez Pieper  
**Email:** esteban.bkk@gmail.com  
**Location:** Da Nang, Vietnam  
**Timezone:** ICT (UTC+7)

**Communication style:**
- Direct, no sugarcoating
- Correct me if overthinking
- Show me results, not just ideas
- Humor is good, but not childish

---

## VERSION HISTORY

**v0.1 (Current):** MVP development phase  
**Target:** Proof of concept with mock execution  
**Status:** In progress

---

**This document is your north star. When in doubt, come back here.**

**Focus on the conversation. Everything else is implementation details.**

**Let's build something useful. 🎯**
