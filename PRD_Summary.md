# Family Financial Advisor — Technical Summary

> **Source:** PRD v1.2 (May 2026) — for the full field-level schemas, pipeline specs, and design decisions log, see `Family_Financial_Advisor_PRD.md`
> **Audience:** Technical stakeholders

---

## TL;DR

An AI-powered conversational financial advisor that treats an Indian family as a single, interconnected financial entity. Built on Claude (Sonnet for conversations, Haiku for classification), it maintains persistent markdown-based memory of every family member's profile, goals, and portfolio, and uses that context to help the family make better decisions over time. It runs locally, stores data on the family's own machine, and never recommends specific securities — recommendations are category-level (equity, debt, term insurance), which keeps the product outside SEBI's definition of "investment advice."

---

## Core Thesis

Most financial tools treat individuals in isolation. This product treats the family as the unit of account. The decisions that change a family's financial trajectory — a primary earner considering a career change, whether to prepay a home loan or invest the surplus, overlapping education funding, retirement with dependents — require seeing interdependencies that no individual-focused tool can reveal. In India, these interdependencies run deeper than most markets: children are supported well into their mid-20s, parents in old age, property is jointly owned, and a single earner's career risk is the entire family's financial risk.

The product operates at the **decision layer**, not the transaction layer. If a decision changes the family's net worth trajectory or cash flow structure, it belongs here. Expense categorisation, portfolio tracking, and budgeting do not.

---

## What This Product Is / Is Not

| This product IS | This product IS NOT |
|---|---|
| A family-context-aware decision support tool | A stock or fund recommendation engine |
| A persistent, memory-rich advisor | An expense tracker or budgeting app |
| A category recommender (equity, debt, hybrid) | A product recommender (HDFC Mid Cap Opportunities) |
| An analysis and education platform | A transaction execution platform |
| A locally-hosted, privacy-first system | A SaaS or cloud product |

**Regulatory positioning:** By recommending categories rather than named securities, the product stays outside SEBI's "investment advice" definition, which requires RIA registration. The agent always uses hedged language ("historically," "typically"), explicitly defers to a SEBI-registered advisor or CA for complex tax/estate/NRI situations, and has a hard guardrail that strips fund names from all responses.

---

## Target Users

**Primary — the family head / family CFO:** The most financially literate person, typically the primary earner. Uses both the chat interface and the dashboard. Has admin access: can view all members' profiles (not private conversations), review recommendations, and edit memory via the dashboard.

**Secondary — other family members:** Parents, spouse, siblings. Interact through chat only. Private conversation histories. Variable financial literacy — the agent adapts response complexity accordingly.

**MVP:** Built for and validated with Vedant's family (Vedant, 24, software engineer; Father, approaching retirement; Mother, conservative FD investor; possible sibling). Single-family, locally-hosted — no multi-tenancy, no account creation flows.

---

## Agent Architecture

### System Diagram

```
User Message
    │
    ├─ [1] CLASSIFIER — Haiku 4.5 (~300ms, ~$0.0003)
    │      Forced tool-use → guaranteed JSON: {context_level, files_to_load, is_followup}
    │
    ├─ [2] ASSEMBLER — pure Python (~50ms, no LLM)
    │      Reads context registry → loads files → computes family aggregate
    │      Builds system blocks with two prompt-cache breakpoints
    │
    ├─ [3] VALIDATOR PRE-PASS — regex strip PAN / account numbers (~1ms)
    │
    ├─ [4] MAIN AGENT — Sonnet 4.6 streaming (~3-8s, ~$0.02-0.04/turn)
    │      Tool-use loop: read_context(), financial_math tools, recall_conversation()
    │
    ├─ [5] VALIDATOR POST-PASS — regex on streamed output (per sentence)
    │      Enforces all 7 hard guardrails before tokens reach the frontend
    │
    ├─ [6] SSE STREAM TO FRONTEND
    │      event: token  data: {"text": "..."}
    │      event: done   data: {"session_id": "...", "turn_id": "..."}
    │
    └─ [7] TRANSCRIPT APPEND — JSONL, no memory writes during session

(Session end: 30-min idle or explicit close)
    └─ SESSION-END SUMMARIZER — Haiku 4.5 (~2s, ~$0.005/session)
           Reads full JSONL → structured JSON → writers layer → atomic file updates
```

### Memory Model

All memory is stored as local markdown files with YAML frontmatter. Markdown was chosen because it is human-readable, editable, git-trackable, and trivially loadable into LLM context. No RAG, no SQLite, no vector database — the total family memory corpus stays well under 30K tokens, so file selection by the classifier is sufficient and transparent.

**Every entry is dated (ISO 8601).** This is non-negotiable: the agent uses dates to reason about freshness, temporal drift, and whether an assumption is still load-bearing.

Memory is organised into three access tiers:

| Tier | When loaded | Budget | Contents |
|---|---|---|---|
| **Tier 1 — Always-loaded** | Every FULL-level turn | ~1.8K tokens | Household context, active member profile, inferences (MED/HIGH), recent conversation summaries, agent notes (retractions), computed family aggregate |
| **Tier 2 — Intent-gated** | When classifier flags as relevant | ~1.5K tokens | Portfolio summary, goals, liabilities, tax, insurance, recommendations log |
| **Tier 3 — Agent-invoked** | Mid-turn via tool call | On demand | Skill playbooks, low-confidence inferences, older conversation excerpts, detailed life events |

**Family aggregate financial state is computed at assembly time** (net worth, savings rate, emergency fund coverage, combined income), never stored as a file — eliminating the stale-cache risk.

**Memory writes happen at session-end only.** During a session, the agent has the full transcript in its prompt context; it doesn't need to re-read freshly-written memory to remember its own outputs. Writing at session-end removes per-turn extraction overhead (~$2.50/month vs ~$25/month) with no functional loss within a session.

### Per-Turn Flow (simplified)

Classifier (Haiku) → Assembler builds two cached system blocks (Tier 1, Tier 2) + uncached skill catalog → pre-pass anonymiser strips PAN/account numbers → Sonnet streams response (calls financial math tools or `read_context()` skill playbooks as needed) → post-pass validator enforces guardrails → SSE to frontend → JSONL append. Session closes on 30-min idle or explicit beacon; Haiku summarizer runs async, writers layer updates memory files atomically.

### Skills Framework

Skills are markdown files in `/skills/` containing advisory guidelines, not rigid rules. They define reasoning patterns and guardrails; the model personalises within them.

| File | Preload | Purpose |
|---|---|---|
| `core_system.md` | Always | Agent identity, tone, fundamental rules |
| `surplus_allocation.md` | Agent-invoked | Two-question framework, priority waterfall, time-horizon allocation table |
| `emergency_response.md` | Agent-invoked | Sudden expense or financial shock |
| `goal_planning.md` | Agent-invoked | Goal extraction, SIP sizing, goal gap analysis |
| `savings_strategy.md` | Agent-invoked | Monthly cash flow, SIP setup, budget review |
| `financial_literacy.md` | Agent-invoked | Definitions, concepts, education |
| `personal_finance.md` | Agent-invoked | Holistic review, multi-topic planning |

The skill catalog (~250 tokens) is always present in the system prompt so the agent knows what to fetch.

---

## Privacy & Guardrails

### Three-Layer Privacy Model

1. **Shared financial fabric** — Portfolio holdings, SIPs, goals, loans, insurance coverage, income bands. Shared by design when joining the family group; this data makes family-context advising possible.
2. **Private conversations** — What a member asks, the scenarios they explore. The agent uses family context to answer but the conversation belongs to the individual. The family head sees conversation summaries, not full transcripts.
3. **Derived insights** — When the agent detects dangerous portfolio overlap, combined equity exposure crossing a threshold, or an insurance gap, the insight surfaces to the dashboard. The conversation that triggered it does not.

**Cross-member write isolation (enforced at the writer layer):** Mom's session can only write to `members/mom/` and `family/`. It cannot write to `members/dad/`. Even if the session summarizer hallucinates a cross-member write, the writer function rejects it. Cross-member observations (Mom mentions Dad's FD) stage to `working/cross_member_observations.md` pending the owning member's confirmation.

**Anonymisation before LLM calls:** Names → "Member A/B/C", account numbers and PAN stripped entirely, bank names → "bank", broker names → "brokerage". A mapping table (in memory, never sent) re-attaches real names in the displayed response.

### Hard Guardrails (Code-Based, Every Response)

| # | Rule | Action |
|---|---|---|
| 1 | No specific securities | Regex strip fund names, tickers, ISINs → replace with category |
| 2 | Allocation bounds | Age + horizon-based equity % max; reject + re-generate if breached |
| 3 | Numerical accuracy | Recalculate any financial math in response; replace if incorrect |
| 4 | Emergency fund gate | If recommending investing and EF is inadequate, inject priority note |
| 5 | Certainty language | Replace "guaranteed/will give/definitely" with "historically/typically/likely" |
| 6 | Recommendation consistency | Compare against last 3 log entries; flag contradiction if circumstances unchanged |
| 7 | Tax implication flag | If response suggests redemption, inject STCG/LTCG note |

**Soft validation (LLM-based, Haiku, high-stakes only):** Triggered for amounts > ₹5L, redemption/restructuring, periodic reviews, or conflicting family goals. Checks logic, potential for misinterpretation, appropriate uncertainty, and jargon level. MVP ships Tier 1 only; Tier 2 added once core loop is stable.

**I-don't-know mode:** The agent explicitly defers on HUF/NRI taxation, estate planning, specific product comparisons, and market timing. Response pattern: "This is something I'd suggest discussing with a [CA/RIA/lawyer]. What I can tell you is [general principle]."

---

## Product Surface

**Onboarding (4 steps):** Family roster (add members, relationships) → brokerage connection (Kite MCP for Zerodha) → quick-fill profiles (income bands, risk, goals — family head fills for all) → one immediate goal. Family head completes setup for everyone; individual onboarding creates insurmountable drop-off.

**Chat interface:** Per-member, streaming, markdown-rendered responses. Each member's conversation history is private. The agent adapts response complexity to financial literacy level.

**Dashboard (family head only):** Family overview (combined net worth, allocation, emergency fund, savings rate), member cards, goals tracker, memory viewer (read-only in MVP), and a "show what was sent to the AI" toggle per message for full transparency.

---

## Data Sources

| Source | What it provides | Method |
|---|---|---|
| Kite MCP (Zerodha) | Holdings, SIPs, transaction history | MCP tool call; daily scheduled refresh |
| Conversation extraction | Goals, life events, preferences, inferences | Haiku session-end summarizer |
| Manual entry (onboarding) | FDs, PPF, NPS, real estate, insurance, income | Prompted by agent during onboarding / conversations |

Multi-brokerage support (Groww, MF Central), Account Aggregator, and statement upload are post-MVP.

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Language | Python 3 | LLM SDK, financial libs, fast iteration |
| Framework | FastAPI + uvicorn | Async, SSE streaming, lightweight |
| Main agent | Claude Sonnet 4.6 | Best balance of quality, cost, tool-use reliability |
| Classifier + summarizer | Claude Haiku 4.5 | Structured JSON; 10× cheaper than Sonnet; ~300ms |
| Memory + transcripts | Markdown files + JSONL | Human-readable, git-trackable, no setup, transparent to LLM |
| Frontend | React + Vite + Tailwind v4 + Zustand | Vedant's stack; fast iteration |
| Streaming | SSE (EventSource) | Standard; FastAPI native |
| Portfolio API | Kite MCP (Zerodha) | Primary brokerage for MVP family |
| Scheduler | APScheduler | Portfolio refresh, session idle watcher |

**Explicitly excluded:** SQLite/RDBMS (markdown file scans are fast at single-family scale; revisit if dashboard latency becomes painful), vector DB / RAG (corpus <30K tokens; direct loading is simpler and more transparent), knowledge graph (domain isn't graph-shaped at ~200 edges), LangChain/LangGraph (pipeline is simple enough; direct SDK is cleaner and more debuggable), Redis (single-machine, no need for caching layers).

---

## MVP Scope

### In Scope

Family onboarding wizard, Kite MCP integration, per-member streaming chat, intent classifier, three-tier memory system, 7 skill files (6 + core_system), session-end Haiku summarizer, all 7 code-based guardrails, cross-member write isolation, anonymisation layer, financial math tools, recommendation tracking with P1/P2/P3 priority, family dashboard, JSONL session transcripts.

### Out of Scope (Post-MVP)

Multi-brokerage support, Account Aggregator, WhatsApp interface, LLM-based soft validator, skills for retirement/education/tax/scenario/comprehensive-review, conflicting goal auto-detection, cross-member soft-confirmation flow, dashboard memory editing, SQLite index layer, statement upload, cloud deployment, multi-tenant, mobile app, notifications, PDF export.

---

## Roadmap

**Phase 2 — Data & channels:** Multi-brokerage (Groww MCP), statement upload (CAS parsing), WhatsApp integration, Account Aggregator.

**Phase 3 — Deeper intelligence:** New skill files (retirement, education, tax, scenario modeling, comprehensive review), advanced calculation tools (tax savings, retirement corpus, Monte Carlo), conflicting goal detection, memory editing UI, cross-member soft-confirmation flow.

**Phase 4 — Scale:** Cloud deployment (Cloud Run), proper auth, subscription billing, mobile app, PDF quarterly reports.

**Phase 5 — Platform (only if validated):** The underlying architecture (family context, multi-persona memory, conversational agent with domain skills) could generalize to health, education, or legal domains. Do not design for this now. Build an exceptional finance product and let the architecture generalize naturally.

---

## Key Design Decisions

| Decision | Why |
|---|---|
| **Category-not-product recommendations** | Keeps product outside SEBI "investment advice" definition; no RIA license needed; removes per-recommendation liability |
| **Three-tier memory, not static prompt** | Always-loading all memory wastes tokens, dilutes attention, and slows responses; the classifier selects what's relevant; Tier 3 lets the agent self-direct deep recall |
| **Memory writes at session-end only** | In-session the agent has the full transcript in context; per-turn writes solve a non-problem at 10× the cost (~$25/mo vs ~$2.50/mo) |
| **Markdown-only, no SQLite** | Human-readable, editable, git-trackable, trivially loadable into LLM context; dashboard queries do file scans, which are fast at single-family scale |
| **No RAG / no vector DB** | Total family corpus <30K tokens; intent-classifier-based file selection is simpler, cheaper, and fully transparent |
| **No knowledge graph** | Domain isn't graph-shaped at MVP scale (~200 edges, traversal depth ≤3); "stale recommendations when assumptions change" is a foreign-key query, not a graph traversal |
| **Cross-member write isolation at the writer layer** | Defence-in-depth: even if the session summarizer hallucinates a write to another member's file, the writer function blocks it |
| **Conversations private, financial data shared** | Full transparency kills adoption; full privacy defeats family-context advantage; the three-layer model balances both |
| **Deterministic math, LLM judgment** | Financial calculations must be exact and reproducible; the LLM personalises within guardrails but never does the math itself |
| **Session boundary = 30-min idle or explicit close** | Midnight boundaries fire mid-conversation and destroy context; the "ambient long session" case is rare and the summarizer handles it |

---

## Open Questions (Unresolved)

1. **Anonymisation of fund names:** "Parag Parikh Flexi Cap" is both a privacy-relevant name and useful category context. Likely solution: send "Flexi Cap Fund A" not the actual name. Needs implementation decision.

2. **Family head transcript access:** Summaries visible (decided); full transcripts not visible (decided); the exact UI for the "summaries visible" flow is still unspecified.

3. **Kite API rate limits:** Daily refresh is the default assumption; actual limits need testing during development.

4. **Per-member vs. family-level recommendations log:** Currently per-member. Defer the merge decision until ~20 recommendations exist and cross-member query patterns are visible.

5. **Floater health insurance location:** Family floater at `family/insurance.md`; term life at `members/{name}/insurance.md`. Mixed schemas in one file vs. splitting — defer until concrete usage clarifies the right schema.
