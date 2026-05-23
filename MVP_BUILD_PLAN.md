# Family Financial Advisor — MVP Build Plan

**Companion to:** `Family_Financial_Advisor_PRD.md` (v1.2)
**Created:** 2026-05-20
**Target duration:** 4–5 days
**Success criterion:** One real family member (not the developer) uses the app unprompted and gets useful financial advice.

---

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| LLM provider | Anthropic only | One SDK, best tool-use reliability, one billing path |
| Main agent model | `claude-sonnet-4-6` (fallback `claude-sonnet-4-5`) | Strongest at hedged language + tool-use |
| Classifier + summarizer model | `claude-haiku-4-5` | 5x cheaper, fast, reliable for structured JSON |
| Dev cost discipline | Use Haiku for main agent during Days 1–2 dev; switch to Sonnet only when pipeline contract is stable (Day 3+) | Stretches the $10 Anthropic credit |
| Prompt caching | `cache_control: {"type": "ephemeral"}` on Tier 1 block from turn 1 | 10x cheaper repeat input |
| Provider abstraction | `backend/agent/llm_provider.py` with single `stream()` method; provider + model in env vars | BYOK-ready for open-source v0.2 |
| Auth for MVP | None — `X-Member-Id` header + localStorage | Solo-family dogfooding doesn't need it |
| Storage | Pure markdown + JSONL + JSON. No SQLite, no DB. | PRD Decision #25 |
| Kite MCP | Skipped for MVP. Manual portfolio entry. | PRD validates family-context thesis without auto-sync |

## Cost budget

| Day | Activity | Estimated burn | Running total |
|---|---|---|---|
| 0 | Pre-flight, smoke tests | $0.10 | $0.10 |
| 1 | Backend pipeline (mostly Haiku) | $0.50 | $0.60 |
| 2 | Real chat UI + transcripts | $2.00 | $2.60 |
| 3 | Classifier + Tier 2 + summarizer | $3.50 | $6.10 |
| 4 | Tool-use loops (3-5x normal cost) | $3.00 | $9.10 |
| 5 | Dogfooding + polish | $1.50 | $10.60 |

**Risk note:** $10 cap leaves zero buffer on Day 4. Top up by $10-20 if at all possible. If hard cap, set up a Gemini fallback key (free tier) as insurance.

## Open decisions to lock on Day 0

1. Top up Anthropic credit to $20-30? — **proceeding with $10**
2. Solo build or paired with friend? — **paired from Day 2**
3. Sonnet 4.6 actually available on this key? — **✅ confirmed**
4. Gemini fallback key set up? — **skipped for now**

---

## Day 0 — Pre-flight (~30 min)

**Goal:** Environment ready, repo scaffolded, model access confirmed. No code yet.

### Checklist
- [ ] Top up Anthropic credit if possible (target $20-30)
- [x] Confirm Sonnet 4.6 + Haiku 4.5 model IDs work on this API key — Haiku: 0.95s $0.000074, Sonnet: 1.45s $0.000384
- [ ] (Optional) Create Gemini API key as free-tier fallback
- [x] Create repo skeleton matching PRD §16:
  - `backend/` (with `agent/`, `tools/`, `utils/` subdirs)
  - `frontend/`
  - `memory/` (with `family/`, `members/`, `working/`)
  - `sessions/`
  - `skills/`
  - `cache/`
- [x] Initialise Python project: `pyproject.toml`, `requirements.txt`
  - Pinned: `fastapi`, `uvicorn[standard]`, `anthropic>=0.40`, `pydantic>=2`, `pydantic-settings`, `python-frontmatter`, `apscheduler`, `python-dotenv`, `httpx`, `sse-starlette`, `pytest` (dev)
- [x] Initialise Vite + React + Tailwind in `frontend/`
  - Installed: `zustand`, `react-markdown`, `remark-gfm`, `tailwindcss @tailwindcss/vite`
- [x] Write `.env.example`
- [x] Hand-author seed memory skeleton for your family:
  - `memory/members/vedant/profile.md` ← **fill in your actual numbers**
  - `memory/family/household.md` ← **fill in other members + fill in their `profile.md` files**
  - (Skip onboarding wizard until Day 5)

### End-of-day verification
```python
python -c "import anthropic; print(anthropic.Anthropic().messages.create(model='claude-haiku-4-5', max_tokens=50, messages=[{'role':'user','content':'hi'}]).content[0].text)"
```
Returns a real response.

**✅ DONE — Both models confirmed. Cost: $0.000458**

---

## Day 1 — Backend pipeline + curl-able streaming endpoint

**Goal:** `POST /chat` streams a real Claude response with Tier 1 memory loaded from seeded markdown. No frontend yet.

### Checklist
- [x] **(1h)** `backend/config.py` — pydantic-settings, env-driven
- [x] **(2h)** `backend/utils/markdown_io.py` — read/write/append/atomic-rename helpers. The **only** module that touches the filesystem.
- [x] **(1h)** `backend/agent/llm_provider.py` — thin interface with one method `stream(messages, system, tools, max_tokens, cache_blocks)`. Anthropic implementation. **BYOK seam.**
- [x] **(1h)** `backend/agent/aggregator.py` — slimmed to `read_family_name()` only; no computed aggregates (LLM anchoring concern; per-member figures still in profile.md). Context registry + assembler built as M4/M5.
- [x] **(2h)** `backend/agent/assembler.py` — Tier 1 + skill/memory catalogue. cache=False hard-off Day 1. Catalogue lists 6 playbooks + 10 memory files (classifier_predicted + agent_invoked) as safety net for missed classifier predictions.
- [x] **(1h)** `backend/agent/orchestrator.py` — pass-through to `provider.stream()`. Day 4 adds tool loop here.
- [x] **(2h)** `backend/main.py` — FastAPI, `POST /chat` SSE, `GET /health`, CORS. SSE event shape frozen.
- [x] **(0.5h)** Author `skills/core_system.md` — proactive question-asking, literacy analogies, advisor persona.
- [x] **(0.5h)** Author `skills/surplus_allocation.md` + 4 additional skill files.
- [x] **(1h)** Manual curl test → all pass (health, 422 missing header, 400 bad member, 200 streaming, session echo)

**Deviations from original plan:**
- Aggregator does NOT compute combined income / surplus / net worth / savings rate — numbers anchor the LLM even with caveats. Raw per-member figures stay in profile.md.
- Skill catalogue expanded to also list all memory files available on demand (fallback for when Day 3 classifier under-predicts).
- M7.1: cache_r=0, cache_w=0 confirmed. Tier 1 is ~1157 tokens; caching hard-off anyway (cache=False on all SystemBlocks Day 1).
- M7.2: Sonnet parity confirmed. Model swap is one env-var flip (`MAIN_AGENT_MODEL=claude-sonnet-4-6`). Sonnet proactively attempted `read_context("financial_literacy")` tool call — skill catalogue working as designed; tool ignored Day 1.

### SSE event shape (FREEZE at end of Day 1)
```
event: token
data: {"text": "..."}

event: done
data: {"session_id": "...", "turn_id": "..."}

event: error
data: {"message": "..."}
```
**Do not change after Day 1.** Frontend depends on this contract.

### End-of-day verification
```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Member-Id: vedant" \
  -d '{"message":"hi, do you know me?"}'
```
Streams a Claude response that correctly references your name and one fact from seeded memory.

### Files created (~10)
- `backend/config.py`, `backend/main.py`
- `backend/utils/markdown_io.py`
- `backend/agent/{llm_provider,aggregator,assembler,orchestrator}.py`
- `skills/{core_system,surplus_allocation}.md`
- `memory/members/vedant/profile.md`, `memory/family/household.md`

**Cost: ~$0.50** (mostly Haiku during dev; one or two Sonnet smoke tests at end of day)

---

## Day 2 — React chat UI + JSONL transcripts + member switcher

**Goal:** Real chat works end-to-end. Multiple members. Transcripts persist to disk.

### Checklist
- [ ] **(1h)** `frontend/src/store/chatStore.js` — Zustand store: messages, streaming flag, activeMember, sessionId
- [ ] **(2h)** `frontend/src/hooks/useChat.js` — SSE consumer; appends streaming tokens; calls `/session/close` on `beforeunload` via `navigator.sendBeacon`
- [ ] **(2h)** `frontend/src/components/Chat.jsx` — chat bubbles, input, submit; uses `react-markdown` + `remark-gfm` for assistant rendering
- [ ] **(1h)** `frontend/src/components/MemberSwitcher.jsx` — dropdown, writes activeMember to Zustand + localStorage
- [ ] **(0.5h)** Send `X-Member-Id` header on every request from frontend
- [ ] **(0.5h)** Add shadcn/ui primitives: `npx shadcn add button input textarea dropdown-menu`
- [ ] **(2h)** `backend/agent/pipeline.py` — orchestration spine: classifier (stubbed for now) → assembler → orchestrator → stream → transcript append
- [ ] **(2h)** `backend/agent/transcripts.py` — JSONL append after stream completes. Schema: `{ts, member, session_id, turn_id, user_msg, assistant_msg, tool_calls:[], intent}`. Use POSIX append (atomic for lines under PIPE_BUF, ~4KB).
- [ ] **(1h)** Session ID logic: backend in-memory dict `{(member, session_id): last_activity_ts}`. New session if no `session_id` cookie OR last activity >30min ago.
- [ ] **(1h)** Cross-session continuity scaffold: assembler reads last 3-5 entries from `memory/members/<m>/conversations.md`. Hand-author 2 sample entries so the path is exercised before Day 3's summarizer ships.

### End-of-day verification
1. Open `http://localhost:5173`
2. Vedant types "what's my emergency fund situation?" → streams a personalised reply
3. Switch to Mom via dropdown
4. Ask a different question → different (Mom-flavored) reply
5. Check disk: `sessions/vedant/<session_id>.jsonl` and `sessions/mom/<session_id>.jsonl` both exist with one line each

### Files created (~8)
- Frontend: `chatStore.js`, `useChat.js`, `Chat.jsx`, `MemberSwitcher.jsx`, `App.jsx`
- Backend: `pipeline.py`, `transcripts.py`

**Cost: ~$2**

---

## Day 3 — Classifier + Tier 2 gating + session-end summarizer + writer isolation

**Goal:** Real classifier drives Tier 2 file loading. Memory actually updates after a session ends. Cross-member writes blocked at the writer layer.

### Checklist
- [ ] **(2h)** `backend/agent/classifier.py` — Haiku call with PRD §6 Stage-1 system prompt. Use Anthropic tool-use forced-choice for reliable JSON. Pydantic schema validates output.
- [ ] **(1h)** `backend/agent/intent_map.py` — typed dict: intent → list of Tier 2 file paths. Implements PRD §6 mapping.
- [ ] **(0.5h)** Follow-up classifier cache: if message <30 chars and previous turn within 60s, reuse previous classification.
- [ ] **(1h)** Wire classifier into `pipeline.py`; assembler now reads `classifier_output.relevant_memory_files` and loads those into Tier 2 block.
- [ ] **(3h)** `backend/agent/writers.py` — one function per memory file (`write_recommendation`, `write_goal`, `write_life_event`, `append_conversation_summary`). Each takes `writer_member_id` and **asserts the target path is in `members/<writer>/` or `family/`**. Atomic write via temp+rename. This is the cross-member isolation enforcement (Decision #27).
- [ ] **(3h)** `backend/agent/memory_updater.py` — session-end summarizer:
  - Haiku call, tool-use forced JSON: `{summary_3_lines, new_recommendations[], new_goals[], life_events_stated[], status_transitions[]}`
  - Reads JSONL transcript from disk, sends as input
  - For each output entry, calls the appropriate writer
  - Idempotent via `sessions/<member>/<session_id>.closed` marker file
- [ ] **(2h)** Session close triggers (both paths converge on `close_session(member, session_id)`):
  - `POST /session/close` endpoint (called by frontend `sendBeacon` on tab unload)
  - APScheduler 60s poll scanning in-memory last-activity dict for sessions idle >30min
- [ ] **(1h)** Author remaining skill files: `skills/{savings_strategy,goal_planning,financial_literacy,emergency_response,personal_finance}.md`
- [ ] **(0.5h)** Switch main agent model from Haiku → Sonnet 4.6 in `.env` now that pipeline is stable

### End-of-day verification
1. Ask: *"where should Mom park ₹5L FD?"*
2. Verify classifier outputs intent `surplus_allocation`
3. Verify assembler loaded `goals.md` + `portfolio_summary.md` + `liabilities.md` + the skill file (check logs)
4. Close the tab (or hit `POST /session/close`)
5. Within ~10s, check:
   - `memory/members/mom/conversations.md` has new 3-line summary entry with date
   - `memory/members/mom/recommendations.md` has new entry with `Date:`, `Priority: P*`, `Status: PROPOSED`, `Assumptions_at_time:`
6. **Cross-member isolation test:** in dev console, manually call `write_recommendation(writer="vedant", target_member="mom", ...)`. Should raise `CrossMemberWriteError`.

### Files created (~9)
- `backend/agent/{classifier,intent_map,writers,memory_updater}.py`
- `skills/{savings_strategy,goal_planning,financial_literacy,emergency_response,personal_finance}.md`

**Cost: ~$3.50**

---

## Day 4 — Tool-use loop + financial_math + validator (trimmed) + dashboard

**Goal:** Numerical accuracy guardrail works end-to-end. Dashboard shows family overview.

### Checklist
- [ ] **(3h)** `backend/tools/financial_math.py` — pure functions. **Write unit tests FIRST** (per CLAUDE.md TDD rule):
  - `calculate_future_value(principal, annual_rate, years, monthly_contribution=0)`
  - `calculate_required_sip(target_corpus, annual_rate, years)`
  - `calculate_goal_gap(target, current, monthly_contribution, annual_rate, years_to_goal)`
  - `check_emergency_fund(monthly_expenses, current_liquid)`
  - `calculate_allocation(age, risk_profile, dependents)`
- [ ] **(2h)** `backend/tools/registry.py` — Anthropic tool definitions for the above. Register in orchestrator. Implement the tool-use loop: stream → `tool_use` block → execute → `tool_result` back → continue stream.
- [ ] **(0.5h)** Smoke-test the loop with a no-op tool first before adding real ones.
- [ ] **(2h)** `backend/agent/validator.py` — implement only 3 of 7 PRD guardrails for MVP:
  - **#1 No specific securities:** regex denylist of common fund names + ticker pattern → replace with category ("HDFC Top 100 Fund" → "a large-cap equity fund")
  - **#5 Certainty language:** regex replace ("guaranteed" → "historically tends to", "will give" → "has historically given")
  - **PII strip on outbound:** PAN regex `[A-Z]{5}[0-9]{4}[A-Z]`, account numbers, before sending to Anthropic API
- [ ] **(1h)** `GET /family/overview` endpoint — calls `aggregator.compute_family_state()` (same function the assembler uses; do NOT duplicate)
- [ ] **(3h)** Frontend dashboard at `/dashboard`:
  - `pages/Dashboard.jsx` — top-level layout
  - `components/FamilyOverview.jsx` — net worth, savings rate, top concerns
  - `components/MemberCard.jsx` — profile + portfolio + active goals (read-only)
  - `components/RecommendationsLog.jsx` — parses all `members/*/recommendations.md`, sortable by date/priority
- [ ] **(1h)** Manual smoke test of validator: ask a question whose natural answer would name a specific fund → verify it gets replaced with category language.

### End-of-day verification
1. Ask: *"Can Mom afford a ₹50L flat in 3 years?"*
2. Verify tool-use loop triggered `calculate_goal_gap` (check logs)
3. Response uses correct numbers
4. Response contains no specific fund names
5. Response uses appropriately uncertain language ("historically tends to" not "will return")
6. Visit `/dashboard` → see combined family net worth, per-member cards, recommendations log sorted by date

### Files created (~7)
- `backend/tools/{financial_math,registry}.py` + `tests/test_financial_math.py`
- `backend/agent/validator.py`
- `frontend/src/pages/Dashboard.jsx`, `frontend/src/components/{FamilyOverview,MemberCard,RecommendationsLog}.jsx`

**Cost: ~$3** (tool-use loops are 3-5x normal turn cost because each tool call is a separate LLM invocation)

---

## Day 5 — Onboarding wizard (trimmed) + recall_conversation + dogfooding + polish

**Goal:** One real family member who is NOT the developer uses the app unprompted and gets real value.

### Checklist
- [ ] **(3h)** Onboarding wizard at `/onboard` (skip Kite MCP entirely; manual entry only):
  - **Step 1:** roster (names + roles + earning status)
  - **Step 2:** per-earner income band + monthly commitments
  - **Step 3:** portfolio quick-fill (FD total, equity total, EPF/PPF balances) — hand-typed
  - **Step 4:** one goal per member, free text
  - `POST /onboard` writes seed markdown atomically; refuses if files exist; add `--reset` CLI for dev iteration
- [ ] **(1h)** `backend/tools/recall_conversation.py` — Tier 3 tool. Anthropic tool registration. Searches across `sessions/<member>/*.jsonl` for keyword match, returns top 3 turns.
- [ ] **(1h)** Add deferred summarizer paths (skipped on Day 3):
  - `inference_candidates[]` → `memory/members/<m>/inferences.md` LOW section
  - `retracted_advice[]` → flip relevant recommendation to `SUPERSEDED` + append note to `agent_notes.md`
- [ ] **(2h) ★ DOGFOODING SESSION** — your mom (or sister) uses the app for one real question, unsupervised. You observe silently. Take notes on what breaks, what's confusing, what's missing.
- [ ] **(2h)** Top **2** fixes from dogfooding session only. **Resist scope creep.** If everything works, polish:
  - Typing indicator while streaming
  - Error state when API is down
  - Empty-state copy in dashboard
  - Basic CSS pass
- [ ] **(1h)** Write `README.md`: setup instructions, BYOK setup section (even though only Anthropic supported in v0.1), env var reference, "how to add your family" guide.

### End-of-day verification
1. Fresh state: `rm -rf memory/ sessions/` (or run `--reset` CLI)
2. Mom (not you) opens the app
3. Mom completes onboarding herself, without your help
4. Mom asks a real financial question
5. Gets a useful, personalised answer with hedged language and no specific fund names
6. Closes tab
7. One hour later, opens again
8. Agent remembers the prior conversation context (via `conversations.md` Tier 1)

### Files created (~5)
- `frontend/src/pages/Onboard.jsx` + wizard step components
- `backend/tools/recall_conversation.py`
- `README.md`

**Cost: ~$1.50**

---

## Critical files (in build order)

These files are load-bearing; subsequent layers depend on their contracts being stable. Build them in this order.

| Order | File | Day | Why critical |
|---|---|---|---|
| 1 | `backend/utils/markdown_io.py` | 1 | Only filesystem touch point |
| 2 | `backend/agent/llm_provider.py` | 1 | BYOK seam — wrong shape here makes future provider swaps painful |
| 3 | `backend/agent/aggregator.py` | 1 | Shared by assembler + dashboard — duplicate logic = diverging numbers |
| 4 | `backend/agent/assembler.py` | 1 | The prompt-assembly contract |
| 5 | `backend/main.py` (SSE event shape) | 1 evening | **FROZEN** once frontend starts |
| 6 | `backend/agent/writers.py` | 3 | Cross-member isolation; must exist before summarizer writes anything |
| 7 | `backend/agent/memory_updater.py` | 3 | Session-end summarizer — product thesis depends on this working |

## Sequencing risks

Avoid these — they each cost half a day of rework:

- **Frontend before SSE contract frozen** → 2-3 rebuilds of stream consumer
- **Classifier before assembler** → classifier output is meaningless without something to consume it
- **Memory writes before writer-layer** → cross-member privacy bug baked in everywhere
- **Dashboard before computed aggregator** → dashboard ↔ assembler numbers diverge by Day 5
- **Tools before tool-use loop verified with no-op tool** → integration debugging tangled with tool debugging

---

## Explicitly OUT OF SCOPE for MVP

Cut from PRD §17 scope to fit the 5-day sprint. All deferred to v0.2:

- **Kite MCP integration** (manual portfolio entry instead — single biggest cut)
- **Full anonymisation mapping table** (regex strip PAN + account # only)
- **Authentication / PIN screen** (`X-Member-Id` header + localStorage)
- **Dashboard memory editing UI** (read-only viewer)
- **"Show what was sent to AI" transparency toggle**
- **4 of 5 Tier 3 tools** (`recall_life_events`, `get_inferences`, `search_recommendations`, `get_portfolio_details`) — only `recall_conversation` ships
- **4 of 7 validator guardrails** (#2, #3, #4, #6, #7) — handled in skill prompts; revisit when failure observed
- **LLM-based Tier 2 soft validation**
- **`pending_writes.md` confirmation flow**
- **`cross_member_observations.md` review UI**
- **Periodic review cron job**
- **Statement upload (CSV/PDF parser)**
- **Session JSONL archival to tar.gz**
- **v0.2 skill files**: `retirement_planning_india`, `education_funding_india`, `tax_planning`, `scenario_modeling`, `comprehensive_plan_review`

---

## Daily ritual

At the end of each day:
1. Tick off completed checklist items in this doc
2. Run the day's verification step
3. Check actual cost vs estimated (Anthropic console)
4. Note anything that surprised you in a `## Day N retro` section (one-liners only)
5. Commit progress with a `feat:` or `chore:` message

If a day runs over by >2h, that's a signal to cut something from the next day, not extend the sprint.
