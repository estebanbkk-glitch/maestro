# Claude Code Prompt: Build Maestro MVP
**Date:** February 5, 2026  
**Model:** Claude Sonnet 4.5 (recommended)  
**Task:** Build initial proof-of-concept for Maestro constraint negotiation system

---

## CONTEXT

I'm building "Maestro" - an intelligent meta-agent that routes tasks to optimal AI tools based on cost, quality, and time constraints. The key innovation is **conversational constraint negotiation** - users and Maestro negotiate tradeoffs transparently.

**Core workflow:**
1. User sends task
2. Maestro analyzes and recommends approach (cost, quality, time estimates)
3. User negotiates ("Can we do $5?")
4. Maestro shows 2-4 options with tradeoffs
5. User picks option
6. Maestro executes

**Key documents uploaded:**
- `meta-agent-concept-manifest.md` (full vision)
- `maestro-constraint-system-update.md` (constraint negotiation details)
- `maestro-commercial-viability.md` (build strategy)

---

## WHAT TO BUILD (MVP - Week 1)

**Goal:** Simple proof-of-concept showing constraint negotiation workflow

**Scope:** Single use case - "scrape N websites and extract data"

**Components needed:**

### 1. Task Analyzer
```python
class TaskAnalyzer:
    """Analyzes user task and extracts parameters"""
    
    def analyze(self, user_input: str) -> Task:
        """
        Input: "Scrape 100 dive shop websites"
        Output: Task(type='scraping', count=100, domain='dive shops')
        """
        pass
```

### 2. Option Generator
```python
class OptionGenerator:
    """Generates execution options with cost/quality/time estimates"""
    
    def generate_options(self, task: Task, constraints: Constraints = None) -> List[Option]:
        """
        Returns 3-4 options with different tradeoffs:
        - Budget option (cheap, lower quality)
        - Balanced option (recommended)
        - Quality option (expensive, high quality)
        - Fast option (if time constraint exists)
        """
        pass
```

### 3. Constraint Negotiator
```python
class ConstraintNegotiator:
    """Handles conversation with user about constraints"""
    
    def present_recommendation(self, options: List[Option]) -> str:
        """Present initial recommendation in natural language"""
        pass
    
    def handle_adjustment(self, constraint: str, value: float) -> str:
        """User said 'Can we do $5?' - show adjusted options"""
        pass
    
    def explain_tradeoffs(self, options: List[Option]) -> str:
        """Explain what user gets with each option"""
        pass
```

### 4. Simple Executor (Mock for now)
```python
class SimpleExecutor:
    """Mock executor - doesn't actually run, just simulates"""
    
    def execute(self, option: Option) -> ExecutionResult:
        """
        Simulate execution with progress updates
        Return: actual cost, quality achieved, time taken
        """
        pass
```

---

## TECHNICAL REQUIREMENTS

### Tech Stack
- **Language:** Python 3.11+
- **CLI:** Rich library for nice terminal output
- **LLM:** Use DeepSeek API for task analysis (cheap)
- **Data:** Simple dict/dataclass, no database yet
- **Config:** YAML for tool pricing and capabilities

### File Structure
```
maestro/
├── __init__.py
├── models.py          # Task, Option, Constraint, ExecutionResult
├── analyzer.py        # TaskAnalyzer
├── generator.py       # OptionGenerator
├── negotiator.py      # ConstraintNegotiator
├── executor.py        # SimpleExecutor (mock)
├── config.py          # Load tool pricing from YAML
├── main.py            # CLI entry point
└── tools.yaml         # Tool definitions and pricing

tests/
├── test_analyzer.py
├── test_generator.py
├── test_negotiator.py
└── test_integration.py

examples/
└── example_session.txt  # Show what a conversation looks like
```

### Configuration Format (tools.yaml)
```yaml
tools:
  scrapy:
    type: scraper
    cost_per_page: 0.0
    success_rate: 0.85
    avg_time_per_page: 0.3
    strengths: [static_html, fast, free]
    weaknesses: [javascript, dynamic_content]
  
  playwright:
    type: scraper
    cost_per_page: 0.0
    success_rate: 0.97
    avg_time_per_page: 2.5
    strengths: [javascript, dynamic_content]
    weaknesses: [slow, resource_heavy]

llms:
  deepseek:
    cost_per_m_input: 0.27
    cost_per_m_output: 1.10
    avg_tokens_per_task: 5000
    strengths: [cheap, fast, structured_data]
    weaknesses: [creativity]
  
  claude:
    cost_per_m_input: 3.00
    cost_per_m_output: 15.00
    avg_tokens_per_task: 8000
    strengths: [reasoning, analysis, quality]
    weaknesses: [cost]
```

---

## EXAMPLE INTERACTION (Target UX)

```
$ python -m maestro

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
  • Full hybrid approach
  • All 100 websites
  💰 Cost: $1.35 ⚠️ ($0.35 over budget)
  ✨ Quality: 92% ✓
  ⏱️  Time: 12 minutes ✓

Which option? (A/B/C)

User> B

Maestro> ✓ Confirmed: Scope reduction approach
  Processing 70 websites with hybrid strategy...

[This is where execution would happen - for MVP, just mock it]

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

## IMPLEMENTATION PRIORITIES

**Phase 1 (This session):**
1. ✅ Set up project structure
2. ✅ Define data models (Task, Option, Constraint, etc.)
3. ✅ Implement OptionGenerator with hardcoded logic
4. ✅ Implement ConstraintNegotiator (formatting & presentation)
5. ✅ Create CLI with Rich for nice output
6. ✅ Mock executor (simulate execution with sleep)

**Phase 2 (Next session):**
1. Add LLM integration for task analysis (DeepSeek API)
2. Load tool definitions from YAML
3. Calculate costs dynamically
4. Add basic preference learning (save user choices)

**Phase 3 (Later):**
1. Real execution (call actual tools)
2. Progress tracking
3. Error handling
4. Multiple use cases (not just scraping)

---

## KEY DESIGN PATTERNS

### 1. Option Generation Strategy
```python
def generate_options(task, constraints=None):
    """
    Always generate 3-4 options:
    1. Budget option (minimize cost, may sacrifice quality/time)
    2. Quality option (maximize quality, may cost more/take longer)
    3. Speed option (minimize time, may cost more/lower quality)
    4. Balanced option (recommended, optimize all three)
    
    If user provides constraint, filter/adjust options accordingly
    """
```

### 2. Constraint Validation
```python
def validate_option(option, constraints):
    """
    Returns: ('pass', []) | ('partial', [violations]) | ('fail', [violations])
    
    - pass: Meets all constraints
    - partial: Minor violations (<10%)
    - fail: Major violations (>10%)
    """
```

### 3. Natural Language Presentation
```python
def format_option(option, user_constraints=None):
    """
    Use emojis and clear formatting:
    💰 Cost: $X.XX [✓ or ⚠️ based on constraints]
    ✨ Quality: XX% [✓ or ⚠️]
    ⏱️  Time: XX min [✓ or ⚠️]
    
    Add explanations for tradeoffs
    """
```

---

## TESTING STRATEGY

**Unit Tests:**
```python
def test_option_generation():
    task = Task(type='scraping', count=100)
    options = generator.generate_options(task)
    assert len(options) >= 3
    assert all(o.cost > 0 for o in options)
    assert all(0 <= o.quality <= 1 for o in options)

def test_constraint_validation():
    option = Option(cost=5.0, quality=0.85, time=600)
    constraints = Constraints(budget_max=3.0)
    status, violations = validator.validate(option, constraints)
    assert status == 'fail'
    assert 'budget' in [v['type'] for v in violations]
```

**Integration Test:**
```python
def test_full_negotiation_flow():
    """Test entire user interaction"""
    # User asks for task
    # Maestro recommends
    # User adjusts constraint
    # Maestro shows options
    # User picks
    # Maestro executes
    # Verify learning is recorded
```

---

## WHAT NOT TO BUILD (Yet)

❌ Real LLM API integration (use mock responses)  
❌ Real tool execution (mock/simulate)  
❌ Database (use in-memory dict)  
❌ Web UI (CLI only)  
❌ Multiple use cases (just scraping)  
❌ Advanced learning (just record choices)  
❌ Auto-provisioning (manual for now)  

**Keep it simple. Prove the core concept first.**

---

## SUCCESS CRITERIA

**You've succeeded if:**
1. ✅ I can run the CLI and have a conversation
2. ✅ Maestro presents options clearly with cost/quality/time
3. ✅ I can negotiate constraints ("Can we do $5?")
4. ✅ Maestro shows 2-4 adjusted options
5. ✅ I can pick an option and see "execution" (mocked)
6. ✅ Code is clean, tested, and documented
7. ✅ I understand how to extend it to real tools

**Time box:** 3-4 hours of coding time

---

## CODING GUIDELINES

**Style:**
- Type hints everywhere
- Docstrings for all public methods
- Use dataclasses for models
- Rich library for pretty output
- Keep functions small (<50 lines)

**Principles:**
- Explicit over implicit
- Simple over clever
- Working over perfect
- Tested over documented (but document too)

**When stuck:**
- Refer back to constraint negotiation workflow
- Ask: "What would make the UX clearer?"
- Mock it first, implement later

---

## QUESTIONS TO ANSWER WHILE CODING

1. How do we calculate estimated cost/quality/time?
   → Start with hardcoded formulas, refine later

2. How many options to show?
   → Always 3-4, never more (choice paralysis)

3. How to handle user saying "yes" to recommendation?
   → Just execute, no more negotiation

4. How to present violations clearly?
   → Use ⚠️ emoji and "X% over/under limit"

5. What if no option meets constraints?
   → Always show closest option + explain tradeoff

---

## FIRST STEPS

1. Create project structure
2. Define data models in `models.py`
3. Implement `OptionGenerator` with hardcoded scraping logic
4. Implement `ConstraintNegotiator` for formatting
5. Create basic CLI with Rich
6. Test the conversation flow

**Start with the models. Get those right, everything else follows.**

---

## REFERENCE DOCUMENTS

The uploaded documents contain:
- Full architectural vision
- Detailed constraint negotiation examples
- Use cases with actual conversations
- Technical component descriptions
- Learning system design

**Read these if you need more context, but you have enough here to start.**

---

## GO BUILD

Focus on making the **negotiation conversation feel natural**.

Cost calculations can be rough.  
Tool selection can be hardcoded.  
Learning can be basic.  

**But the negotiation UX must feel right.**

That's the core innovation. Everything else is implementation details.

Good luck! 🎯

---

**END OF PROMPT**
