# Day 1 Milestones — Family Financial Advisor MVP Backend

## Context

Day 0 is complete (deps installed, `.env` configured, model smoke tests passed). Day 1 ships a single deliverable: a `POST /chat` SSE endpoint that streams a real Claude response with Tier 1 memory loaded. No frontend, no classifier (hardcoded), no Tier 2 files, no tools, no validator, no memory writes.

Architecture is locked in `agentic_workflow.md`. This document only sequences the work; it does not redesign.

### Locked decisions (from this planning session)
- **Main model on Day 1:** Haiku 4.5 (one Sonnet smoke test at end of day).
- **Seed memory content:** Deferred — discuss separately. End-of-day verification relaxed (response must reference "Vedant" by name; financial-fact criterion gated on memory decision).
- **`context_registry.py`:** Built as a real module on Day 1.
- **Missing Tier 1 files:** Skip-if-missing with logged warning. Required: `household.md`, active member's `profile.md`, `skills/core_system.md`.

### Frozen contracts at end of Day 1
1. SSE event names + JSON payload schemas (`token`/`done`/`error`).
2. `LLMProvider.stream()` signature (BYOK seam).
3. `StreamEvent` dataclass union (`TextDelta`/`ToolUseRequest`/`StreamEnd`/`StreamError`).
4. `SystemBlock(text, cache)`.
5. `ClassifierOutput` TypedDict (Day 3 classifier must emit exactly this).
6. `AssembledPrompt` dataclass.
7. `ContextEntry` dataclass.
8. `FamilyAggregate` dataclass (dashboard reads same object Day 4).
9. System-block ordering: `[Tier1, Tier2?, skill_catalog]`.
10. `X-Member-Id` request header.

### Greppable invariants
- Only `backend/utils/markdown_io.py` may contain `open(`, `os.replace`, `Path.read_*`, `Path.write_*`.
- Only `backend/agent/llm_provider.py` may `import anthropic`.

---

## Milestone 1 — Configuration & Filesystem Foundation (~90 min)

**Goal:** Settings load from `.env`; the single filesystem-touching module reads seeded markdown.

**Dependencies:** None — root of the graph.

### Micro-tasks
- [x] **1.1** Create `backend/config.py` with a `Settings(BaseSettings)` Pydantic class. Fields: `anthropic_api_key` (required), `llm_provider` (default `"anthropic"`), `main_agent_model` (default `"claude-haiku-4-5-20251001"`), `classifier_model` (default `"claude-haiku-4-5-20251001"`), `summarizer_model` (default `"claude-haiku-4-5-20251001"`), `memory_dir` (`Path("memory")`), `skills_dir` (`Path("skills")`), `sessions_dir` (`Path("sessions")`), `max_response_tokens` (`2048`), `enable_cache` (`True`), `cors_origins` (`["http://localhost:5173"]`).
- [x] **1.2** Add `project_root: Path = Path(__file__).resolve().parent.parent` and a `resolve(p: Path) -> Path` helper.
- [x] **1.3** Export module-level `settings = Settings()` singleton.
- [x] **1.4** Create empty `backend/__init__.py`, `backend/agent/__init__.py`, `backend/utils/__init__.py`, `backend/tools/__init__.py` to mark them as packages.
- [x] **1.5** Create `backend/utils/markdown_io.py` with sync functions:
  - `read_markdown(path: Path) -> str` (raises `FileNotFoundError`)
  - `read_markdown_or_none(path: Path) -> str | None`
  - `strip_frontmatter(content: str) -> str` (via `python-frontmatter`)
  - `list_member_dirs(memory_root: Path) -> list[str]`
- [x] **1.6** Add forward-compatible write stubs (declared, not exercised Day 1):
  - `write_markdown_atomic(path: Path, content: str) -> None` (temp + `os.replace`)
  - `append_markdown(path: Path, content: str) -> None`
  - `append_jsonl(path: Path, record: dict) -> None`
  - `touch_marker(path: Path) -> None`, `marker_exists(path: Path) -> bool`

### Verification
```bash
cd /Users/vedantshah/Desktop/family_finance_advisor
python -c "from backend.config import settings; assert settings.anthropic_api_key; print('config OK')"
python -c "from backend.utils.markdown_io import read_markdown, strip_frontmatter; \
c = read_markdown('memory/members/vedant/profile.md'); \
print(strip_frontmatter(c)[:200])"
```

---

## Milestone 2 — LLM Provider (BYOK Seam) (~75 min)

**Goal:** Streaming Anthropic call works end-to-end, isolated from FastAPI.

**Dependencies:** M1 (config).

### Micro-tasks
- [x] **2.1** In `backend/agent/llm_provider.py`, define frozen dataclasses: `SystemBlock(text: str, cache: bool=False)`, `TextDelta(text: str)`, `ToolUseRequest(tool_use_id, name, input)`, `StreamEnd(stop_reason, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens)`, `StreamError(message, code)`.
- [x] **2.2** Define `StreamEvent = TextDelta | ToolUseRequest | StreamEnd | StreamError` type alias.
- [x] **2.3** Define `LLMProvider` Protocol with one method:
  ```python
  async def stream(*, system: list[SystemBlock], messages: list[dict],
                   tools: list[dict] | None = None,
                   max_tokens: int = 2048,
                   model: str | None = None) -> AsyncIterator[StreamEvent]
  ```
- [x] **2.4** Implement `AnthropicProvider`:
  - Constructor: `__init__(api_key: str, default_model: str)`.
  - Uses `anthropic.AsyncAnthropic`.
  - Renders `SystemBlock` → `{"type":"text","text":...,"cache_control":{"type":"ephemeral"}}` when `cache=True AND settings.enable_cache`.
  - Uses `client.messages.stream(...)` async context manager.
  - Maps Anthropic events: `content_block_delta` (text_delta) → `TextDelta`; `content_block_start` with `type=tool_use` → `ToolUseRequest`; `message_stop` + usage → `StreamEnd`.
  - Catches `anthropic.APIError` → yields `StreamError(message=..., code=...)`, never raises.
- [x] **2.5** Implement `get_provider() -> LLMProvider` factory reading `settings.llm_provider`.
- [x] **2.6** Add `if __name__ == "__main__"` block: streams "count to three" via a tiny async runner.

### Verification
```bash
python -m backend.agent.llm_provider
# Expect: tokens streaming to stdout, ending with "three" (or similar)
```
Cost: < $0.001.

---

## Milestone 3 — Skill Files Authored (~60 min, can run in parallel with M2)

**Goal:** Two markdown skill files exist on disk. No code yet.

**Dependencies:** None — independent track.

### Micro-tasks
- [x] **3.1** Create `skills/core_system.md` (~300-500 tokens). Authored from first principles (not lifted from PRD example), redesigned to be WhatsApp-conversational, scope-strict, literacy-adaptive with analogies, and non-moralizing. 352 words / ~475 tokens.
- [x] **3.2** Create `skills/surplus_allocation.md` (~400-600 tokens). Redesigned: no fixed horizon table (reasoning principles instead), risk calibrated via loss scenarios not self-report, no family-context hooks (assembler handles), 3-gate waterfall. 440 words / ~595 tokens.
- [x] **3.3** Sanity check: `wc -w` — core_system 352w, surplus_allocation 440w. Both within target range.

Note: `surplus_allocation.md` is `agent_invoked` — not loaded by the assembler on Day 1, but ships now so the file inventory is honest and Day 4's tool plumbing finds it.

---

## Milestone 4 — Context Registry + Aggregator (~75 min)

**Goal:** Declarative context metadata module + pure family-state computation function.

**Dependencies:** M1 (markdown_io, config).

### Micro-tasks
- [x] **4.1** Create `backend/agent/context_registry.py`. No imports from other `agent/*` modules; no I/O.
- [x] **4.2** Define `PreloadPolicy = Literal["always", "classifier_predicted", "agent_invoked"]`.
- [x] **4.3** Define frozen `ContextEntry(name, path_template, description, preload, scope, required=False)` dataclass.
- [x] **4.4** Populate `REGISTRY: tuple[ContextEntry, ...]` — 21 entries total: 5 always, 8 classifier_predicted, 8 agent_invoked. Required: family.household, member.profile, skill.core_system.
- [x] **4.5** Add pure helpers: `entries_by_policy(policy)`, `entry_by_name(name)`, `resolve_path(entry, member, project_root)`.
- [x] **4.6** Create `backend/agent/aggregator.py`. Define `MemberSnapshot` and `FamilyAggregate` frozen dataclasses.
- [x] **4.7** Implement `compute_family_state(memory_root: Path) -> FamilyAggregate` — reads all member profiles, never raises, captures parse errors as notes.
- [x] **4.8** Implement `parse_profile_md(content: str, member_id: str) -> MemberSnapshot` — YAML frontmatter (role, earning_status) + regex bullet extraction. `[fill in]` → None.
- [x] **4.9** Implement `render_aggregate_markdown(agg: FamilyAggregate) -> str` — member table + summary stats, — for missing fields, data-gaps note at end.

### Verification
```bash
python -c "from backend.agent.context_registry import REGISTRY, entries_by_policy; \
print('total:', len(REGISTRY), 'always:', len(entries_by_policy('always')))"

python -c "from backend.agent.aggregator import compute_family_state, render_aggregate_markdown; \
from backend.config import settings; \
agg = compute_family_state(settings.resolve(settings.memory_dir)); \
print(render_aggregate_markdown(agg))"
```

---

## Milestone 5 — Prompt Assembler (~90 min)

**Goal:** Given an active member + hardcoded classifier output, produce the exact system blocks + messages list that the orchestrator passes to the provider.

**Dependencies:** M1, M2 (SystemBlock import), M3 (skill files exist), M4 (registry + aggregator).

### Micro-tasks
- [x] **5.1** Create `backend/agent/assembler.py`.
- [x] **5.2** Define `ClassifierOutput` TypedDict: `context_level: Literal["MINIMAL","FULL"]`, `relevant_memory_files: list[str]`, `is_followup: bool`.
- [x] **5.3** Define frozen `AssembledPrompt(system: list[SystemBlock], messages: list[dict], context_level, debug: dict)` dataclass.
- [x] **5.4** Define `AssemblyError(Exception)`.
- [x] **5.5** Implement `assemble(...)` with MINIMAL + FULL branches. FULL: Tier 1 = session context + always entries + aggregate (4993 chars, cache=False). Tier 2 skipped (empty list). Skill catalog = 6 playbook entries. Family name derived from household.md frontmatter — no hardcoding in source.
- [x] **5.6** Cache hard-off (cache=False on all SystemBlocks, Day 1 decision). No per-request values in Tier 1. `grep -ri "shah" backend/` returns zero hits.

### Verification
```bash
python -c "
from backend.agent.assembler import assemble
from backend.config import settings
o = assemble(
    active_member='vedant',
    classifier_output={'context_level':'FULL','relevant_memory_files':[],'is_followup':False},
    in_session_history=[],
    user_message='hi, do you know me?',
    memory_root=settings.resolve(settings.memory_dir),
    skills_root=settings.resolve(settings.skills_dir),
)
print('blocks:', len(o.system))
print('tier1 length:', len(o.system[0].text))
print('tier1 cache:', o.system[0].cache)
print('tier1 preview:', o.system[0].text[:400])
print('debug:', o.debug)
"
```
Eyeball: no `[fill in]` artifacts crash render; tier1 cache=True; user message NOT in system blocks; debug["missing"] lists optional files we don't have.

---

## Milestone 6 — Orchestrator + FastAPI Endpoint (~120 min + 30 min buffer)

**Goal:** `POST /chat` SSE endpoint runs end-to-end. `curl -N` streams a Haiku response.

**Dependencies:** M2 (provider), M5 (assembler).

### Micro-tasks
- [ ] **6.1** Create `backend/agent/orchestrator.py`. Single async generator `run_turn(*, provider, prompt, tools=None, max_tokens=2048, model=None) -> AsyncIterator[StreamEvent]` — straight pass-through to `provider.stream(...)` on Day 1.
- [ ] **6.2** Create `backend/main.py`. Boilerplate: FastAPI app, CORS middleware (`allow_origins=settings.cors_origins`), `EventSourceResponse` import from `sse_starlette.sse`.
- [ ] **6.3** Define `ChatRequest(BaseModel)`: `message: str`, `session_id: str | None = None`.
- [ ] **6.4** Implement `POST /chat`:
  - Extract `x_member_id: str = Header(..., alias="X-Member-Id")`.
  - Generate `session_id = body.session_id or uuid4().hex`; `turn_id = "t01"`.
  - Call `assemble(active_member=x_member_id, classifier_output={"context_level":"FULL","relevant_memory_files":[],"is_followup":False}, in_session_history=[], user_message=body.message, memory_root=..., skills_root=...)`.
  - Catch `AssemblyError` → return HTTP 400 with detail; do NOT open stream.
  - Build SSE event source generator: iterate `run_turn(...)`, map events:
    - `TextDelta` → `{"event": "token", "data": json.dumps({"text": ev.text})}`
    - `StreamError` → `{"event": "error", "data": json.dumps({"message": ev.message})}`, then return
    - `StreamEnd` → `{"event": "done", "data": json.dumps({"session_id": session_id, "turn_id": turn_id})}`, then return
    - `ToolUseRequest` → ignore on Day 1 (Day 4 wires up)
  - Wrap generator body in `try/except Exception` → emit generic `error` event with `"internal_error"`, log full traceback server-side.
  - Return `EventSourceResponse(event_source())`.
- [ ] **6.5** Implement `GET /health` → `{"status": "ok", "model": settings.main_agent_model}`.
- [ ] **6.6** Verify Pydantic + FastAPI imports parse: `python -c "import backend.main"`.

### Verification
```bash
uvicorn backend.main:app --reload --port 8000
# in another shell:
curl http://localhost:8000/health
# → {"status":"ok","model":"claude-haiku-4-5-20251001"}

curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Member-Id: vedant" \
  -d '{"message":"hi, do you know me?"}'
```
Expect: `event: token` lines streaming, then exactly one `event: done`. No `event: error`. Response mentions "Vedant" by name.

---

## Milestone 7 — End-of-day verification + Sonnet parity check (~30 min)

**Goal:** Cache behavior confirmed (if prefix ≥1024 tokens), Sonnet parity smoke test passes, SSE event shape frozen.

**Dependencies:** M6.

### Micro-tasks
- [x] **7.1** cache_r=0 cache_w=0 confirmed via direct provider call. Tier 1 = ~1157 tokens; cache hard-off (cache=False on all SystemBlocks Day 1). Revisit when seed memory grows past ~1024 tokens.
- [x] **7.2** Sonnet parity confirmed (`MAIN_AGENT_MODEL=claude-sonnet-4-6`). Clean stream. Sonnet proactively called `read_context("financial_literacy")` — skill catalogue working; tool ignored Day 1.
- [x] **7.3** SSE event shape frozen: `# SSE event shape FROZEN at end of Day 1 — do not change without updating frontend (Day 2)` added to `backend/main.py`.
- [x] **7.4** `MVP_BUILD_PLAN.md` Day 1 checklist marked complete with deviations noted.

### Pass criteria (verbatim from MVP_BUILD_PLAN.md, relaxed per locked decisions)
- Stream begins within ~2s.
- ≥1 `event: token` line before `event: done`.
- `event: done` arrives with non-empty `session_id` and `turn_id`.
- No `event: error`.
- Server logs show successful Anthropic API call, no tracebacks.
- Response references "Vedant" by name.
- **Stretch criterion (gated on deferred memory decision):** response references a specific financial fact.

---

## Risk register (top 5)

| # | Risk | Mitigation |
|---|---|---|
| 1 | Anthropic streaming SDK shape mismatch on `anthropic>=0.40` | M2 standalone script validates streaming in isolation. Log first 5 raw events on first run. |
| 2 | `cache_control` silently fails because Tier 1 prefix < 1024 tokens with placeholder content | M7.1 checks cache_read tokens. Accept no caching Day 1 if prefix too small. |
| 3 | Missing optional Tier 1 files (`conversations.md`, `calendar.md`, `agent_notes.md`) | Locked: skip-if-missing, log warning. Assembler uses `read_markdown_or_none`. |
| 4 | `sse-starlette` event format pickiness — `data` must be a JSON string | Always `json.dumps()` the payload. Test with `curl -N`. |
| 5 | FastAPI streaming exception swallow | M6.4 wraps generator body in try/except → explicit error event before propagation. Verify by deliberately raising. |

---

## Cost expectation

- Per-turn on Haiku 4.5 with Day 1 prompt size (~600-1500 input tokens): ~$0.001-0.002.
- 50-turn dev session on Haiku: ~$0.05-0.10.
- M7.2 Sonnet parity smoke test: ~$0.01.
- **Day 1 total: well under the $0.50 budget.**

---

## Parking lot (deliberately deferred)

- **Seed memory content** — `memory/members/vedant/profile.md` and `memory/family/household.md` still contain `[fill in]` placeholders. User wants to discuss separately. Revisit before Day 2 frontend dogfooding.
- All Day 2-5 features (frontend, transcripts, classifier, Tier 2 loading, writers, summarizer, tool-use loop, validator, dashboard, onboarding wizard, `recall_conversation`, README).

---

## Critical paths

To be created in order (M1 → M7):
1. `/Users/vedantshah/Desktop/family_finance_advisor/backend/__init__.py` (empty)
2. `/Users/vedantshah/Desktop/family_finance_advisor/backend/agent/__init__.py` (empty)
3. `/Users/vedantshah/Desktop/family_finance_advisor/backend/utils/__init__.py` (empty)
4. `/Users/vedantshah/Desktop/family_finance_advisor/backend/tools/__init__.py` (empty)
5. `/Users/vedantshah/Desktop/family_finance_advisor/backend/config.py`
6. `/Users/vedantshah/Desktop/family_finance_advisor/backend/utils/markdown_io.py`
7. `/Users/vedantshah/Desktop/family_finance_advisor/backend/agent/llm_provider.py`
8. `/Users/vedantshah/Desktop/family_finance_advisor/skills/core_system.md`
9. `/Users/vedantshah/Desktop/family_finance_advisor/skills/surplus_allocation.md`
10. `/Users/vedantshah/Desktop/family_finance_advisor/backend/agent/context_registry.py`
11. `/Users/vedantshah/Desktop/family_finance_advisor/backend/agent/aggregator.py`
12. `/Users/vedantshah/Desktop/family_finance_advisor/backend/agent/assembler.py`
13. `/Users/vedantshah/Desktop/family_finance_advisor/backend/agent/orchestrator.py`
14. `/Users/vedantshah/Desktop/family_finance_advisor/backend/main.py`

Source-of-truth references:
- `/Users/vedantshah/Desktop/family_finance_advisor/agentic_workflow.md` (architecture)
- `/Users/vedantshah/Desktop/family_finance_advisor/Family_Financial_Advisor_PRD.md` §6, §7
- `/Users/vedantshah/Desktop/family_finance_advisor/MVP_BUILD_PLAN.md` Day 1
- `/Users/vedantshah/Desktop/family_finance_advisor/smoke_test.py` (Anthropic SDK reference)
