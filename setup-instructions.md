# How to Start Building Maestro with Claude Code
**Date:** February 5, 2026

---

## STEP 1: Prepare Your Files

**Create a project folder:**
```powershell
mkdir D:\maestro-mvp
cd D:\maestro-mvp
```

**Copy these documents into the folder:**
1. `claude-code-prompt.md` (the main prompt)
2. `meta-agent-concept-manifest.md` (reference)
3. `maestro-constraint-system-update.md` (reference)

---

## STEP 2: Configure Claude Code

**Model Recommendation: Sonnet 4.5**

**Why not Opus 4.5?**
- You have VERY detailed specs (no ambiguity)
- Sonnet is 80% cheaper ($3 vs $15 per M input)
- Sonnet is excellent for well-defined code generation
- Save Opus for when you hit architectural ambiguity

**Cost estimate:**
- **Sonnet 4.5:** ~$20-30 for MVP
- **Opus 4.5:** ~$100-150 for MVP
- **Savings:** $80-120 (4-5x more iterations)

**When to switch to Opus:**
- If Sonnet gets stuck on architecture decisions
- If you need deeper reasoning about tradeoffs
- If quality isn't meeting expectations

---

## STEP 3: Start Claude Code

**From PowerShell:**
```powershell
cd D:\maestro-mvp
claude-code
```

**Or if you want to specify model:**
```powershell
claude-code --model claude-sonnet-4-5-20250929
```

---

## STEP 4: Give Claude Code the Prompt

**Option A: Paste the whole prompt**
```
You: [Copy entire contents of claude-code-prompt.md and paste]
```

**Option B: Reference the file**
```
You: Read claude-code-prompt.md and start building the Maestro MVP as described. Focus on the constraint negotiation conversation flow first.
```

**Option C: Conversational (recommended)**
```
You: I want to build Maestro - a meta-agent that negotiates constraints with users. The key innovation is conversational negotiation: user asks for task, Maestro suggests approach with cost/quality/time, user negotiates ("can we do $5?"), Maestro shows 2-4 options, user picks, Maestro executes.

Read claude-code-prompt.md for full spec. Let's start with the MVP - just the scraping use case, mock execution, focus on making the negotiation conversation feel natural.

Start by creating the project structure and data models.
```

---

## STEP 5: What to Expect

**Claude Code will:**
1. Ask clarifying questions (answer based on the prompt)
2. Create file structure
3. Implement models first (Task, Option, Constraint)
4. Build OptionGenerator with hardcoded logic
5. Build ConstraintNegotiator for conversation
6. Create CLI with Rich library
7. Write tests

**Typical session:**
- 30-60 minutes of back-and-forth
- 5-10 files created
- You'll test it, give feedback, iterate

---

## STEP 6: Testing the MVP

**Once Claude Code is done:**
```powershell
cd D:\maestro-mvp
python -m maestro
```

**You should see:**
```
Maestro> Hello! What task can I help with?

You> Scrape 100 dive shop websites

Maestro> [Shows recommendation with cost/quality/time]

You> Can we do $5?

Maestro> [Shows 3 options with tradeoffs]

You> Option B

Maestro> [Simulates execution]
```

**If it works → You've proven the concept!**

---

## STEP 7: Next Iterations

**After MVP works, add:**
1. Real LLM integration (DeepSeek API for task analysis)
2. Load tool configs from YAML
3. Save user preferences
4. Better cost calculations
5. More use cases

**Each iteration:** 1-2 hour session with Claude Code

---

## TROUBLESHOOTING

**If Claude Code asks "What should I do next?"**
→ Say: "Follow the claude-code-prompt.md priorities. Start with models.py"

**If code doesn't run:**
→ Say: "There's an error: [paste error]. Please fix it."

**If conversation flow feels wrong:**
→ Say: "The negotiation doesn't feel natural. Make it more conversational like in the examples."

**If Claude Code gets stuck:**
→ Switch to Opus 4.5: `claude-code --model claude-opus-4-5-20251101`

---

## MODEL SWITCHING MID-SESSION

**If Sonnet struggles:**
```powershell
# Stop current session (Ctrl+C)
# Restart with Opus
claude-code --model claude-opus-4-5-20251101

# Then say:
You: Continue from where we left off, but use Opus-level reasoning for the architecture decisions. [Explain what's not working]
```

**Cost comparison if you switch:**
- Already spent: ~$10 on Sonnet
- Remaining with Opus: ~$50-80
- Still cheaper than starting with Opus: ~$100-150

---

## FILES YOU'LL HAVE AFTER MVP

```
D:\maestro-mvp\
├── claude-code-prompt.md          (your prompt)
├── meta-agent-concept-manifest.md (reference)
├── maestro-constraint-system-update.md (reference)
├── README.md                       (Claude Code creates this)
├── requirements.txt                (dependencies)
├── pyproject.toml                  (project config)
│
├── maestro\
│   ├── __init__.py
│   ├── models.py                   (data structures)
│   ├── generator.py                (option generation)
│   ├── negotiator.py               (conversation)
│   ├── executor.py                 (mock execution)
│   ├── config.py                   (load YAML)
│   └── main.py                     (CLI entry point)
│
├── tests\
│   ├── test_generator.py
│   ├── test_negotiator.py
│   └── test_integration.py
│
├── tools.yaml                      (tool definitions)
└── examples\
    └── example_session.txt         (sample conversation)
```

---

## COST TRACKING

**Keep an eye on Claude Code's token usage:**

```powershell
# Claude Code shows tokens after each interaction
# Rough estimate:
# - Each back-and-forth: 5-10k tokens
# - Full MVP: 50-100k tokens total
# 
# Sonnet cost: 50k input × $3/M + 100k output × $15/M = $0.15 + $1.50 = $1.65 per iteration
# 
# Full MVP (~10 iterations): ~$16.50
```

**If costs exceed $30 on Sonnet, something's wrong:**
- Too much regeneration (bad prompts)
- Not following instructions
- Missing context

**Switch to focused prompts or pause to reassess.**

---

## SUCCESS CHECKLIST

After your first Claude Code session, you should have:

✅ Working CLI that runs
✅ Conversation flow that feels natural
✅ Can negotiate constraints ("can we do $5?")
✅ Shows 2-4 options with clear tradeoffs
✅ Mock execution runs (with fake progress)
✅ Code is tested
✅ You understand the codebase

**If you have all of these → Phase 1 complete!**

---

## WHAT TO DO AFTER MVP

1. **Test it yourself** - run through 5-10 scenarios
2. **Show someone** - get feedback on UX
3. **Document learnings** - what works, what doesn't
4. **Plan next iteration** - LLM integration? More use cases?

**Don't jump ahead.** Validate each step before adding complexity.

---

## FINAL TIPS

1. **Let Claude Code lead on code structure**
   - It knows Python best practices
   - It will suggest good patterns
   - Trust it unless it violates the prompt

2. **Be specific in feedback**
   - ❌ "This doesn't feel right"
   - ✅ "The cost formatting should show $ with 2 decimals"

3. **Iterate quickly**
   - Don't try to be perfect first time
   - Get it working, then refine
   - Working > Perfect

4. **Save versions**
   - Commit to git after each working iteration
   - Easy to rollback if something breaks

5. **Take breaks**
   - Claude Code sessions can be intense
   - Step away, test manually, come back with feedback

---

## READY?

You have:
✅ The full prompt
✅ Model recommendation (Sonnet 4.5)
✅ Cost estimates
✅ Setup instructions
✅ Troubleshooting guide

**Now go build it.**

```powershell
cd D:\maestro-mvp
claude-code
```

**First message to Claude Code:**
"Read claude-code-prompt.md and let's build the Maestro MVP. Start with project structure and models."

---

**Good luck! 🚀**

---

**END OF GUIDE**
