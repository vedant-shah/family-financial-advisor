# Agentic Workflow

**Companion to:** `Family_Financial_Advisor_PRD.md` (v1.2), `MVP_BUILD_PLAN.md`
**Created:** 2026-05-21

Documents the backend agent architecture — models, context loading, per-turn flow, session lifecycle, and the reasoning behind each design choice.

---

## Philosophy

The harness does the heavy lifting so the model doesn't have to. By controlling exactly what context is loaded, when, and by whom, we:

- Reduce the base model requirement (Sonnet is sufficient; Opus not needed for MVP)
- Enable prompt caching for significant cost savings
- Keep the agent focused on advice generation, not on figuring out what data it needs

Good harness engineering means a well-scaffolded Sonnet outperforms an unscaffolded Opus on a specialized domain.

---

## Models and Their Roles

| Model | Role | Rationale |
|---|---|---|
| **Claude Sonnet 4.6** | Main conversational agent — the advisor the family talks to | Best balance of quality, cost, tool-use reliability for financial reasoning |
| **Claude Haiku 4.5** | Classifier + session-end summarizer | Structured JSON tasks; 10x cheaper than Sonnet; fast (~300ms) |
| **Claude Opus** | Not used in MVP | Overkill; revisit for v0.2 complex scenarios (retirement modeling, multi-member tax optimization) |

**Haiku extended thinking:** Available but disabled by default. Enable on the session-end summarizer for sessions with >20 turns or multiple topic switches — memory writes are permanent, the extra thinking tokens are cheap insurance on edge cases.

---

## Context Architecture

### The Context Registry

Memory files and skill files are the same primitive: **named markdown blobs the agent can read**. There is no architectural distinction between them. The only differentiator is when they are loaded.

Every context file has one entry in the registry:

```python
{
    "name": str,               # used as the tool argument (read_context(name))
    "path": str,               # filesystem path (relative to project root)
    "description": str,        # shown in the system prompt skill catalog
    "preload": Literal["always", "classifier_predicted", "agent_invoked"]
}
```

### Preload Policies

**`always`** — Loaded unconditionally for every FULL-level turn. Small, identity-critical content the agent always needs.

| File | Content |
|---|---|
| `family/household.md` | Joint accounts, shared expenses, family roster |
| `members/<m>/profile.md` | Age, role, income, employment, retirement targets |
| `members/<m>/conversations.md` | Last 3-5 session summaries |
| `family/calendar.md` | Recurring events + future state changes |
| _(computed)_ | Family aggregate financial state — net worth, savings rate, emergency fund coverage — computed live by `aggregator.py`, not a file |

**`classifier_predicted`** — Loaded when the classifier flags them as likely relevant to the current message. Tier 2 in PRD terminology.

| File | Relevant for |
|---|---|
| `members/<m>/portfolio_summary.md` | Investment / allocation questions |
| `members/<m>/goals.md` | Goal planning, surplus allocation |
| `members/<m>/liabilities.md` | Loan questions, debt management |
| `members/<m>/risk_profile.md` | Allocation, investment recommendations |
| `members/<m>/tax.md` | 80C/80D, ELSS, capital gains questions |
| `members/<m>/insurance.md` | Coverage assessment |
| `members/<m>/income_expenses.md` | Cash flow, savings rate questions |
| `family/inferences.md` | Cross-member financial observations (HIGH confidence only) |

**`agent_invoked`** — Never preloaded. Exposed as a tool. Agent fetches when its reasoning decides it's needed.

| File | When agent fetches it |
|---|---|
| `skills/surplus_allocation.md` | Deploying spare cash (FD vs MF, lump sum vs SIP) |
| `skills/emergency_response.md` | Sudden expense or financial shock |
| `skills/goal_planning.md` | Setting or modifying a financial goal |
| `skills/savings_strategy.md` | Monthly cash flow, SIP setup |
| `skills/financial_literacy.md` | Definitions, concepts, education |
| `skills/personal_finance.md` | Holistic review, multi-topic |
| `members/<m>/inferences.md` (LOW section) | When low-confidence observations may be relevant |
| `members/<m>/agent_notes.md` | Prior agent reasoning, superseded recommendations |

### Skill Catalog in System Prompt

The system prompt always includes a brief catalog of all `agent_invoked` skill files (~250 tokens). The agent uses this to decide what to fetch:

```
AVAILABLE PLAYBOOKS — call read_context(name) when handling these question types:
- surplus_allocation:  deploying spare cash (FD vs MF, lump sum vs SIP decisions)
- emergency_response:  sudden expense or financial shock
- goal_planning:       setting or modifying a financial goal
- savings_strategy:    monthly cash flow, SIP setup, budget review
- financial_literacy:  definitions, concepts, financial education
- personal_finance:    holistic review, multi-topic planning
```

The agent reads the full skill when its reasoning suggests a playbook is useful. For simple turns ("what does ELSS mean?") it may answer from training knowledge directly.

---

## Context Levels

### MINIMAL

**What's loaded:** Identity stamp (~100 tok) + in-session history + user message. No Tier 1, no Tier 2.

**Used for:** Pure social turns — greetings, acknowledgments ("thanks", "ok", "noted", "got it"), small talk with no financial content.

**Response latency:** ~1-2s (no context to load)

### FULL

**What's loaded:** Always-preloaded Tier 1 + classifier-predicted Tier 2 + skill catalog + in-session history + user message.

**Used for:** Anything touching money, goals, accounts, investments, planning, or financial decisions.

**Rule:** When uncertain between MINIMAL and FULL → **always FULL**. A FULL misclassification wastes a few tokens. A MINIMAL misclassification means the agent has no memory and gives generic, context-free advice.

---

## Per-Turn Flow

Complete backend lifecycle for one user message. Example: Mom types *"should I move my ₹5L FD to mutual funds?"*

```
User message arrives at POST /chat
│
├─ [1] SESSION BOOKKEEPING  (~5ms)
│      Check (member, session_id) in in-memory dict
│      last_activity > 30min or no session_id → new session, new UUID
│      Update last_activity = now()
│
├─ [2] CLASSIFIER — Haiku 4.5  (~300ms, ~$0.0003)
│      Input:  current message + last 1-2 turns for context
│      Output: {context_level, relevant_memory_files, is_followup}
│      Method: Anthropic forced tool-use → guaranteed valid JSON schema
│
│      Follow-up cache:
│        if len(message) < 30 chars AND previous turn < 60s ago
│        → reuse previous classifier output, skip Haiku call
│
│      Conservative bias (in classifier prompt):
│        "Any financial noun (FD, SIP, EMI, loan, goal...) → FULL"
│        "When uncertain between MINIMAL and FULL → return FULL"
│        "Multi-topic messages → union of all relevant files"
│
│      Example output for Mom's FD question:
│      {
│        "context_level": "FULL",
│        "relevant_memory_files": [
│          "members/mom/portfolio_summary",
│          "members/mom/goals",
│          "members/mom/liabilities",
│          "members/mom/risk_profile"
│        ],
│        "is_followup": false
│      }
│
├─ [3] ASSEMBLER — pure function, no LLM  (~50ms)
│      Reads preload policy from context registry
│      Computes family aggregate state via aggregator.py (shared
│        with GET /family/overview — same function, no divergence)
│
│      MINIMAL branch:
│        system = [identity_stamp]
│        messages = in_session_history + [user_message]
│
│      FULL branch:
│        system = [
│          {
│            text: always_files + aggregate_state,   ← Tier 1
│            cache_control: {type: "ephemeral"}      ← cache breakpoint 1
│          },
│          {
│            text: classifier_predicted_files,        ← Tier 2
│            cache_control: {type: "ephemeral"}      ← cache breakpoint 2
│          },
│          {
│            text: skill_catalog                     ← no cache (small + varies)
│          }
│        ]
│        messages = in_session_history + [user_message]
│
├─ [4] VALIDATOR PRE-PASS — regex  (~1ms)
│      Strip from outbound payload before Anthropic API call:
│        - PAN numbers: [A-Z]{5}[0-9]{4}[A-Z]
│        - Account numbers: patterns >8 digits in financial context
│      Content with raw PII never leaves the server
│
├─ [5] MAIN AGENT — Sonnet 4.6 streaming  (~3-8s, ~$0.02-0.04/turn)
│      Receives assembled system + messages + registered tools
│
│      May emit tool_use blocks mid-stream. For each:
│        Stream pauses → backend executes tool → tool_result returned → stream resumes
│
│      TOOLS AVAILABLE:
│      ┌─────────────────────────────────────────────────────────────┐
│      │ read_context(name: str)                                     │
│      │   Returns full content of any agent_invoked file           │
│      │   Used for: skill playbooks, inferences, agent notes       │
│      │   Registered: all agent_invoked entries in context registry │
│      ├─────────────────────────────────────────────────────────────┤
│      │ calculate_future_value(principal, rate, years, monthly=0)  │
│      │ calculate_required_sip(target, rate, years)                │
│      │ calculate_goal_gap(target, current, monthly, rate, years)  │
│      │ check_emergency_fund(monthly_expenses, liquid_savings)      │
│      │ calculate_allocation(age, risk_profile, dependents)        │
│      │   All pure functions in backend/tools/financial_math.py    │
│      │   No LLM call — results are deterministic                  │
│      ├─────────────────────────────────────────────────────────────┤
│      │ recall_conversation(query: str)                            │
│      │   Searches sessions/<member>/*.jsonl for keyword match     │
│      │   Returns top 3 matching turns from past sessions         │
│      │   Tier 3 tool — only invoked when explicit recall needed  │
│      └─────────────────────────────────────────────────────────────┘
│
│      Example tool call sequence for Mom's FD question:
│        1. read_context("surplus_allocation")   ← agent decides it needs playbook
│        2. calculate_future_value(500000, 7, 5) ← FD path
│        3. calculate_future_value(500000, 10, 5) ← hybrid MF path
│        → Streams response using both results
│
├─ [6] VALIDATOR POST-PASS — regex on streamed output  (per sentence boundary)
│      Guardrail #1 — no specific securities:
│        "HDFC Top 100 Fund" → "a large-cap equity fund"
│        "Reliance Industries" → "this company's stock"
│      Guardrail #5 — certainty language:
│        "guaranteed returns" → "historically tends to return"
│        "will give you" → "has historically given"
│        "will definitely" → "is likely to"
│
├─ [7] SSE STREAM TO FRONTEND
│      event: token   data: {"text": "...chunk..."}
│      event: done    data: {"session_id": "abc123", "turn_id": "t03"}
│      event: error   data: {"message": "..."}
│
│      Frontend useChat.js appends tokens to Zustand store
│      React re-renders the growing message bubble in real time
│
└─ [8] TRANSCRIPT APPEND  (~5ms, no memory writes)
       One JSONL line appended to sessions/<member>/<session_id>.jsonl:
       {
         "ts": "2026-05-21T15:23:11Z",
         "member": "mom",
         "session_id": "abc123",
         "turn_id": "t03",
         "user_msg": "should I move my ₹5L FD to mutual funds?",
         "assistant_msg": "<full validated response>",
         "tool_calls": [
           {"name": "read_context", "args": {"name": "surplus_allocation"}},
           {"name": "calculate_future_value", "args": {...}, "result": 701276},
           {"name": "calculate_future_value", "args": {...}, "result": 805255}
         ],
         "context_level": "FULL",
         "intent": "surplus_allocation",
         "tier_2_files_loaded": ["portfolio_summary", "goals", "liabilities", "risk_profile"],
         "tokens": {"input": 5847, "cache_read": 4210, "cache_write": 0, "output": 612}
       }

       NO memory writes during a session.
       The agent has the full transcript in context — it knows what it said
       in turn 2 when it's on turn 5. Writes happen at session-end only.
```

---

## Session Lifecycle

### Opening

New session triggered when:
- No `session_id` header from frontend (first message)
- `last_activity` for `(member, session_id)` was >30 minutes ago

### Closing

Two triggers, both converge on `close_session(member, session_id)`:

1. **Frontend beacon:** `navigator.sendBeacon('/session/close', {session_id})` fired on tab unload
2. **Backend idle watcher:** APScheduler polls every 60s, closes sessions idle >30min

`close_session` is idempotent — checks for `.closed` marker file before doing any work.

### Session-End Memory Update — Haiku 4.5 (~2s, ~$0.005/session)

```
close_session(member="mom", session_id="abc123") called
│
├─ Check sessions/mom/abc123.closed → bail if already processed
│
├─ Read full JSONL transcript for this session
│
├─ HAIKU CALL (extended thinking optional for long/complex sessions):
│    Forced tool-use JSON output — structured extraction, not summarization:
│    {
│      "summary_3_lines": [
│        "2026-05-21: Mom asked about moving ₹5L FD to mutual funds.",
│        "Agent recommended ₹2L liquid emergency buffer + ₹3L in 60/40 hybrid.",
│        "Mom did not commit; said she would think about it."
│      ],
│      "new_recommendations": [
│        {
│          "text": "Reallocate ₹5L: keep ₹2L liquid, invest ₹3L in 60/40 hybrid",
│          "priority": "P2",
│          "source": "AGENT_PROPOSED",
│          "assumptions_at_time": "FD rates 7%, hybrid MF expected 9-10%, 5yr horizon",
│          "status": "PROPOSED"
│        }
│      ],
│      "new_goals": [],
│      "life_events_stated": [],
│      "status_transitions": [],
│      "inference_candidates": [
│        {"text": "Mom prefers capital preservation over upside", "confidence": "LOW"}
│      ]
│    }
│
└─ WRITERS LAYER — backend/agent/writers.py
     One function per memory file type. Each write:
       - Asserts writer_member_id ∈ {member, "family"}
       - Raises CrossMemberWriteError on cross-member write attempt
       - Writes atomically: temp file → rename

     summary_3_lines      → append dated entry to members/mom/conversations.md
     new_recommendations  → append to members/mom/recommendations.md
     new_goals            → append to members/mom/goals.md
     life_events_stated   → append to members/mom/life_events.md
     status_transitions   → update status field in recommendations.md
     inference_candidates → append to members/mom/inferences.md (LOW section)

     Write sessions/mom/abc123.closed marker → done
```

Total per-session cost: ~$0.005. For a family of 4 doing 8 sessions/day: ~$1.20/month.

---

## Prompt Caching

Two cache breakpoints, 5-min TTL each. Caching strategy is revisited after one real month of usage data — frequency, session length, and intent distribution all affect the optimal TTL choice.

```
System prompt layout:

┌─ BLOCK 1: Tier 1 stable content (~5,000 tokens) ──────────────────┐
│  family/household.md + member profile + conversation summaries +   │
│  calendar + family aggregate state (computed)                       │
│  → cache_control: {type: "ephemeral"}   ← breakpoint 1, 5-min    │
└────────────────────────────────────────────────────────────────────┘

┌─ BLOCK 2: Tier 2 intent-specific content (~1,500 tokens) ─────────┐
│  classifier-predicted memory files for this turn's intent          │
│  → cache_control: {type: "ephemeral"}   ← breakpoint 2, 5-min    │
└────────────────────────────────────────────────────────────────────┘

┌─ UNCACHED: skill catalog + in-session history + user message ──────┐
│  ~250 tok skill catalog + variable history + ~100 tok message      │
│  Not cached — changes every turn                                   │
└────────────────────────────────────────────────────────────────────┘
```

**Cache hit cost:** $0.30/MTok vs $3/MTok base (Sonnet 4.6). 10x cheaper on repeated input.

**Within a session:** Tier 1 cache hits every turn after the first. Tier 2 hits when intent stays the same across turns.

**Critical rule:** Never put timestamps, session IDs, or any per-request values inside cached blocks. Prefix must be 100% identical for cache to activate.

**Minimum cacheable size:** 1,024 tokens for Sonnet 4.6. Tier 1 (~5K tokens) comfortably exceeds this.

---

## Why Not Pure Agentic (Remove the Classifier)?

If the agent is truly agentic — has tools, makes decisions — why not let Sonnet decide what files it needs directly?

**Two concrete reasons it doesn't work:**

**Cost.** Letting Sonnet self-route means 1-3 tool-call round-trips before the agent can respond. Each Sonnet call costs ~$0.015-0.025. The Haiku classifier costs $0.0003. The question "what files does this message need?" is a pattern-matching problem, not a reasoning problem. Paying Sonnet prices for it is wasteful.

**Caching breaks.** Preloaded content in the system prompt is cacheable with `cache_control`. Tool results arriving as `tool_result` messages in the conversation are not cacheable. Removing the classifier eliminates the 10x cache savings on Tier 1.

The classifier makes a **routing decision** (what data is needed?). The agent makes a **reasoning decision** (what advice to give?). These are separable concerns requiring different levels of intelligence.

---

## Key Design Principles

**1. Harness reduces model requirements.**
Good context loading means Sonnet does what Opus would do unscaffolded. Skills and memory are loaded surgically — the agent's job is reasoning and generation, not retrieval.

**2. Memory and skills are the same primitive.**
Both are markdown files exposed via the same registry. Differentiated only by preload policy, not by type. One `read_context(name)` tool, one registry entry format.

**3. Classifier handles routing. Agent handles reasoning.**
The classifier predicts which data files are needed (cheap, Haiku). The agent decides which skill playbooks to consult (reasoning, agent-invoked). Neither does the other's job.

**4. Misclassification is recoverable.**
The agent has `read_context` as a fallback. A missing file → agent fetches it via tool (one round-trip). The dangerous case (MINIMAL when FULL is needed) is handled by conservative bias in the classifier prompt — any financial noun triggers FULL.

**5. No memory writes during a session.**
The agent has the current session transcript in context — it doesn't need to "save" what it just said mid-conversation. All writes happen at session-end in one atomic batch via the Haiku summarizer.

**6. All memory writes go through writers.py.**
This is the only module that modifies memory files. Cross-member write isolation (Decision #27 in PRD) is enforced exclusively here — no other code touches memory files directly.

**7. Aggregate state is one function, two callers.**
`aggregator.py` computes the family financial state. Both the assembler (Tier 1 preload) and the dashboard endpoint (`GET /family/overview`) import and call the same function. Numbers never diverge.

---

## File Map

```
backend/
├── config.py                    # env-driven settings (pydantic-settings)
├── main.py                      # FastAPI app, POST /chat, GET /family/overview, POST /session/close
├── agent/
│   ├── llm_provider.py          # thin LLM interface: stream(messages, system, tools, ...)
│   │                            # Anthropic implementation; BYOK seam for v0.2
│   ├── classifier.py            # Haiku call → {context_level, relevant_memory_files}
│   ├── context_registry.py      # all context files: name, path, description, preload policy
│   ├── assembler.py             # builds system + messages from registry + classifier output
│   ├── aggregator.py            # computes family aggregate state (shared with dashboard)
│   ├── orchestrator.py          # wraps llm_provider.stream(); handles tool-use loop
│   ├── pipeline.py              # orchestration spine: classifier → assembler → orchestrator
│   │                            #   → validator → stream → transcript append
│   ├── validator.py             # guardrails #1 (securities) + #5 (certainty language) + PII strip
│   ├── memory_updater.py        # session-end Haiku summarizer
│   ├── writers.py               # memory file writers; enforces cross-member isolation
│   └── transcripts.py           # JSONL append; session ID management
├── tools/
│   ├── financial_math.py        # pure functions: calculate_future_value, calculate_required_sip, etc.
│   ├── registry.py              # Anthropic tool definitions for financial_math + read_context + recall
│   └── recall_conversation.py  # searches sessions/*.jsonl for keyword match
└── utils/
    └── markdown_io.py           # ONLY module that touches the filesystem; atomic write helpers
```
