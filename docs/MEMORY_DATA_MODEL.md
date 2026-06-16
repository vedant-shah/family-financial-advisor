# Memory Data Model

The contract every writer targets: **onboarding forms, document uploads, and
conversation extraction all write the same store.** One reconcile mechanism
governs all of them.

This document is the source of truth for *what information we keep, where it
lives, and how it is updated*. It supersedes the implicit model currently split
across `backend/agent/context_registry.py`, the writers, and hand-edited
markdown.

---

## 1. Core principles

1. **One source of truth.** A fact lives in exactly one structured file. The
   live advisor reads it; onboarding/upload/conversation all write it.
2. **Provenance on every fact.** We always know where a value came from, how
   sure we are, and how fresh it is — so a recalled number never silently
   overwrites a bank statement.
3. **History is never destroyed.** Updates supersede (append the new
   authoritative value + mark the old one superseded). The trajectory of a
   number is itself advisory signal.
4. **Cross-member isolation.** A writer acting as member X may only write under
   `members/X/` or `family/`. Observations about another member are *staged*,
   never written directly into their files (§7).
5. **Single-member-first** (§9). The app works fully for one member alone;
   other members' data is purely additive.
6. **Files earn separateness from mode/lifecycle/loading, not size**, and are
   **created lazily** — a fact-less category is simply no file, never an empty
   one. Merge concerns that share a mode and a loading trigger and stay small.
7. **The main agent has the full catalogue.** Every file is registered with a
   description, so the agent can pull any of them on demand mid-conversation;
   the catalogue marks what is already loaded vs available-on-demand.

## 2. The update modes

Every file is exactly one mode. The mode is a **property of the file**, so the
stage-2 reconciler knows how to treat a candidate from its target file alone.

| Mode | Meaning | Reconcile action |
|---|---|---|
| **append** | Something that happened and stays true | Insert (dedup by id) |
| **current-value** | A fact with a latest value that changes | Match → supersede old, insert authoritative; old entry kept, marked superseded |
| **dated-log** | A time series of full snapshots | Always insert a new dated snapshot; never supersede |
| **narrative** | Free prose the pipeline never parses | Human/agent only |

## 3. Provenance fields

Every **current-value** and **dated-log** entry carries:

| Field | Values | Purpose |
|---|---|---|
| `source` | `onboarding_form` \| `onboarding_quiz` \| `document_upload` \| `brokerage_sync` \| `conversation` \| `inference` | Who asserted it |
| `confidence` | `low` \| `med` \| `high` | How much to trust it (source implies a default) |
| `as_of` | `YYYY-MM-DD` | Date the value was *true* |
| `last_updated` | `YYYY-MM-DD` | Date the entry was *written* |

**Source-authority precedence** (governs supersede):

```
document_upload ≈ brokerage_sync  >  conversation  >  onboarding_form ≈ onboarding_quiz  >  inference
```

> **Self-stated facts are authoritative** (decision 2026-06-16). A first-person
> conversational statement outranks the onboarding form: the user is the source
> of truth, and a later correction ("I actually earn 1.15, not 1.2") should
> supersede the older form value cleanly rather than stage silently. Objective
> documents/syncs (uploads, brokerage) remain the guardrail *above* conversation —
> a casual remark still never overrides a bank statement.

A lower-authority candidate does **not** silently overwrite a higher one. It is
either **superseded-but-flagged** (written with its low confidence + a
`needs_confirmation` note) or **staged** to `working/discrepancies.md` for the
next session/dashboard to confirm. A materially fresher low-authority value
(e.g. "I switched jobs, income is higher now") may supersede-but-flag; it never
clobbers silently. (Full policy: §8.)

---

## 4. Per-member layout — `memory/members/<member>/`

### Current-value (structured, provenance, supersede-on-match)

| File | Holds | Seeded by | Updated by |
|---|---|---|---|
| `profile.md` | Identity: name, role, age, relationships, earning status, financial literacy. **No money figures.** | Onboarding P1 | rarely (life events) |
| `finances.md` | Cash flow + debt: income streams, recurring expenses, liabilities. Sections: Income / Expenses / Liabilities. Each item: label, amount, cadence (`monthly`/`annual`/`one_time`), + provenance | Onboarding P2 | conversation (flagged), upload |
| `portfolio_summary.md` | Current investment holdings by class (equity, MF/SIP, FD, EPF/PPF, other) — the *current* picture | Onboarding P2 upload | portfolio reviews, conversation (flagged) |
| `goals.md` | Short/long-term goals; each: title, target (figure), horizon, status (`ACTIVE`/`ACHIEVED`/`DROPPED`) | Onboarding P3 | conversation (refine/complete/cancel) |
| `risk_profile.md` | **Current** revealed risk stance: risk tolerance + investment horizon, with basis/confidence | Onboarding behavioral quiz | conversation (evidence-accrual) |
| `inferences.md` | Behavioral layer (loss aversion, decision style, financial anxiety, liquidity psychology); each: claim, basis, confidence, evidence-trail | conversation | conversation (evidence-accrual) |

> **finances.md merge:** income, expenses, and liabilities share the
> current-value mode, stay small at single-member scale, and read better
> together (surplus/net-worth reasoning). Kept separate are the files with a
> genuinely distinct mode or lifecycle: portfolio (dated-log behind it),
> risk_profile (soft-update inference), goals (own lifecycle), inferences.
>
> **Goals & risk_profile note:** these supersede, but *softly* for inferences —
> see §10. Fix the loose `goals.md` schema (the current on-disk goal has an empty
> `Target:`); `target` is required at write time or the goal is staged, not
> written blank.

### Dated-log (append snapshots, full history)

| File | Holds | Written by |
|---|---|---|
| `portfolio_snapshots.md` | Full holdings statement per upload/review, one `## as of YYYY-MM-DD` block with the whole picture | Onboarding P2 upload + every portfolio review |

> `portfolio_summary.md` (current) is the latest snapshot folded with any
> piecemeal conversation updates; `portfolio_snapshots.md` is the immutable
> time series behind it.

### Append-only (log, idempotent/dedup'd)

| File | Holds |
|---|---|
| `conversations.md` | Dated session summaries (3 lines each) |
| `recommendations.md` | Advice given (title, priority, assumptions/basis, status). **Must be in the context registry — currently never loaded back.** |
| `life_events.md` | Stated events — occurred or anticipated (job change, new child, planned move) |
| `agent_notes.md` | Status transitions, retractions, superseded-pointers, open threads (open threads live here until they earn their own file) |

### Narrative (never parsed by the pipeline)

| File | Holds |
|---|---|
| `narrative.md` | Free prose / human notes (the old `profile.md` "Notes" section lands here) |

---

## 5. Family layout — `memory/family/`

| File | Mode | Holds |
|---|---|---|
| `household.md` | current-value | Roster + family tree, shared tax status, shared liabilities/assets (joint home loan, property) |
| `calendar.md` | append | Recurring events and future state changes (referenced by registry; create) |
| `inferences.md` | current-value | Cross-member, **high-confidence** observations |

> The **family aggregate** (net worth, combined surplus, savings rate) is
> **computed at assembly time, never stored** — it is derived from member
> current-value files so it can never go stale, and is marked **PARTIAL** when
> members are missing data (§9).

## 6. Staging — `memory/working/`

| File | Holds |
|---|---|
| `cross_member_observations.md` | Observations one member's conversation made about *another* member, pending promotion (§7) |
| `discrepancies.md` | Conflicts between a low-authority candidate and a higher-authority stored value, pending confirmation (§8) |

---

## 7. Cross-member information handling

Three distinct cases:

1. **Shared / joint facts** (joint home loan, jointly-owned property, combined
   income) → written at **family scope** (`family/household.md` or family
   financial sections). Allowed by isolation, since `family/` is a permitted
   target for any writer.
2. **One member's conversation reveals something about another member**
   ("my dad is retiring next year") → the isolation rule forbids writing into
   the other member's files. It is **staged** to
   `working/cross_member_observations.md`, tagged with the source member and
   date. It is **never auto-written** into the other member's tree.
3. **Cross-member patterns** ("the family is collectively over-weighted in real
   estate") → `family/inferences.md` (high-confidence only).

**Promotion of a staged observation** (case 2): surfaced for confirmation at the
start of the observed member's next session (or via a review/dashboard). On
confirmation, written into that member's file with `source: conversation (via
<member>)` and confidence per the confirmation. No silent cross-writes, ever.

## 8. Ambiguity vs conflict policy

These are different and handled differently:

- **Conflict** (two values for the same fact): the §3 authority precedence
  decides; a lower-authority source never silently overwrites a higher one.
  Equal-authority genuine contradictions are **supersede-but-flagged** or
  **staged** to `working/discrepancies.md` for confirmation. Within one
  conversation, the correction-aware rule wins (latest word).
- **Ambiguity** (can't tell what the item refers to, or the value is vague): the
  extractor must **not fabricate a confident fact**. Policy: **"when unsure,
  stage — don't assert."** Skip it, or record it as a low-confidence open thread
  to revisit, rather than writing a guess into durable memory. (Write-side
  counterpart of the prompt's "if you can't point to a basis, don't record it.")

## 9. Single-member-first

The common case (and the validated one) is a single member using the app. This
is a **first-class, fully-working mode**, not a degraded one.

- The app works fully for the active member with zero other-member data.
- **Absent members are never fabricated.** Others may sit in the family tree as
  roster entries with no financial/profile data.
- The **family aggregate is marked PARTIAL** when members lack data — never
  present a half-family net worth as complete.
- **Optional proxy data:** the solo user may give rough info about others
  ("dad's retired, has a pension"), stored as **low-confidence proxy**
  (`source: conversation`, flagged unverified), usable cautiously.
- The advisor is **honest about the gap** ("I only have your picture, not your
  spouse's") rather than silently reasoning on a hole.

Multi-member is purely additive context that improves the family view when
present.

---

## 10. Inference update rule (special case)

Inferences (incl. `risk_profile.md`) are current-value but **must not flip on a
single remark**. A new observation:

1. Matches an existing inference by *topic* (e.g. "risk tolerance").
2. **Adds to the evidence trail** and **nudges confidence**, rather than
   overwriting the claim outright.
3. Only supersedes the claim itself when evidence clearly contradicts the prior
   claim; the superseded entry is kept (the trajectory — e.g. growing more
   cautious near retirement — is signal).

The **onboarding behavioral quiz** (2–3 scenario yes/nos) writes the *first*
`risk_profile.md` entry as a *revealed* stance (`source: onboarding_quiz`,
`confidence: med`) — never a self-labeled checkbox.

---

## 11. Onboarding → file mapping

| Phase | Collects (buttons/sliders, minimal text) | Writes |
|---|---|---|
| **P1 — Who** | Family tree, names, ages, roles, relationships, earning status | `profile.md` (each member) + `family/household.md` roster |
| **P2 — Money** | Income, assets, liabilities; Excel/PDF upload auto-analyzed | `finances.md`, `portfolio_summary.md` + first `portfolio_snapshots.md` entry |
| **P3 — Goals** | Short/long-term goals | `goals.md` |
| **Behavioral quiz** | 2–3 risk scenarios | first `risk_profile.md` entry |

---

## 12. Conversation extraction → file mapping (post-onboarding)

Stage 1 extracts candidates (no memory access); stage 2 loads only the target
file per candidate and reconciles per that file's mode.

| Extracted candidate | Target file | Mode | Notes |
|---|---|---|---|
| `summary_3_lines` | `conversations.md` | append | |
| `recommendations` | `recommendations.md` | append | |
| `status_transitions` | `agent_notes.md` | append | |
| `life_events` | `life_events.md` | append | occurred or anticipated |
| `financial_fact_updates` | `finances.md` | current-value | `source: conversation`, `confidence: low`; equal/higher authority supersedes, a lower-authority conflict auto-stages to `working/discrepancies.md` (never clobbers an upload). **v1: finances only** — conversational portfolio holdings are out of scope (uploads own balances). |
| `goal_updates` | `goals.md` | current-value | action→lifecycle (set/refine=ACTIVE, complete=ACHIEVED, cancel=DROPPED); set/refine with no target is dropped (not written blank); complete/cancel also leaves a pointer in `agent_notes.md` |
| `inferences` (incl. risk) | `inferences.md` / `risk_profile.md` | current-value (soft, §10) | **accrue, not flip**: insert if the topic/dimension is new, else append evidence + nudge confidence one notch with the claim UNCHANGED. Revising the claim itself is a deferred confirmation path. |
| `cross_member_observations` | `working/cross_member_observations.md` | append (staging) | observation about another person → staged for confirmation (§7); never written into that member's tree |

**Boundaries (write into the extractor prompt):**
- Onboarding/upload own the *initial* value of every structured fact;
  conversations own *changes* and the entire soft layer.
- Conversations **report changes and reveal behavior; they do not author
  balances.** Exact holdings/balances are owned by upload/sync.
- A conversation mentioning another member **stages** an observation (§7); it
  does not mutate the family roster.
- **When unsure, stage — don't assert** (§8).

**v1 implementation notes (override as the pipeline matures):**
- Inferences **accrue** (never auto-flip): stage 1 is memory-free, so it cannot
  judge "contradicts a stored claim"; the reconciler therefore inserts a new
  topic or accrues evidence + nudges confidence, and a true claim reversal is a
  deferred confirmation path rather than an automatic supersede.
- Goal/inference matching is **exact-key** (title / topic); a rephrased goal
  creates a new one rather than refining it — a later stage-2 semantic match can
  fix this if it gets noisy.
- Cross-member *patterns* (`family/inferences.md`, §7 case 3) are **deferred**;
  only single-member facts and staged cross-member *observations* are wired.

---

## 13. Information-type inventory (the complete set)

**Hard facts (structured, owned by onboarding/upload, updated by conversation):**
identity & family tree · income · recurring expenses · liabilities ·
portfolio holdings (current + dated snapshots) · goals.

**Soft layer (owned by conversation):**
revealed risk tolerance + horizon · loss aversion · decision style · financial
anxiety baseline · liquidity/cash psychology · life events · advice given +
status · session summaries · open threads.

**Derived, never stored:** family aggregate / net worth / savings rate.

**Deferred (do not build yet):** insurance, tax facts (regime/80C), dependents
as a distinct entity (lives in profile/household), transaction-level data
(explicitly anti-scope), separate `decisions` file (lives in summary for now).

---

## 14. Judgment calls made here (override if you disagree)

1. **Cash-flow financials merged into one `finances.md`** (income + expenses +
   liabilities); portfolio, risk_profile, goals, inferences kept separate for
   their distinct mode/lifecycle. Earlier planning floated either one combined
   file or a full per-topic split; this is the middle: merge same-mode-and-small,
   split genuinely-distinct.
2. **`risk_profile.md` kept as its own file** (the one promoted, classifier-
   loaded inference) separate from the broader `inferences.md`.
3. **`recommendations.md` added to the read path** (registry) — today it is
   written but never loaded, so past advice is invisible to the live advisor.
4. **Portfolio kept as BOTH** a current summary and a dated-snapshot log, per the
   requirement to store every review/upload log-style with an `as_of` date.

## 15. Implementation impact (build phase, not done here)

- Split `profile.md` → structured `profile.md` + `narrative.md`; move money out
  to `finances.md` / `portfolio_summary.md`. (Migration is cheap now — almost no
  real data.)
- Add writers: `write_financial_fact` (→ finances.md), `write_inference`,
  `write_risk_profile`, `write_portfolio_snapshot`, `write_goal` (supersede),
  + a shared supersede helper (append authoritative + mark old superseded)
  honoring §3 precedence, + staging writers for `working/`.
- Extend writers to accept `source` / `confidence` / `as_of`.
- Update `context_registry.py`: **register every file with a clear description**
  (recommendations, life_events, portfolio_snapshots, finances, working/* as
  appropriate) so the agent's on-demand catalogue (§1.7) is complete; confirm
  each entry's mode.
- Extend the extractor schema with `financial_fact_updates`, `goal_updates`,
  `inferences`; wire the two-stage reconcile in `_dispatch`, including the §7
  cross-member staging and §8 ambiguity/conflict handling.

---

## 16. ADR — Agentic surgical edit for write-back reconciliation (2026-06-15)

> Status: **accepted**. Supersedes the "exact-key matching" half of §12's v1
> notes. The §1–§11 data model, modes, provenance, and authority precedence are
> unchanged — this ADR only changes *how the extractor decides what to write*.

### Context

The §12 v1 pipeline runs the extractor **blind**: stage 1 reads only the
transcript (no memory access) and emits flat candidate lists; stage 2 routes
each candidate to a writer that matches on an **exact key** (`category.label`).
A memory-free extractor cannot know an existing block exists, so it re-states
facts under slightly different labels. Observed on live data
(`members/vedant/finances.md`):

- **#2 duplicate fact, two keys** — `expense.total` (onboarding, 25000) and
  `expense.personal spending` (conversation, 25000) coexist as two CURRENT
  blocks for the same money.
- **#6 key-name drift** — free-form labels (`expense.mutual fund SIPs`) diverge
  from the onboarding schema; exact-key matching can never reconcile them.
- **#4 / #5 mis-categorization** — `income.previous salary` stored as CURRENT;
  a SIP filed under `expense`. (Addressed separately by the prompt-tightening
  slice + model upgrade.)

Exact-key matching is the root cause of #2/#6: only a reader that *sees* the
existing block can tell "personal spending" is the same fact as "total".

### Decision

**Agentic surgical edit**, modeled on how Claude Code manages file-based memory:

1. The extractor is given the **relevant existing memory file(s)** for the
   member, with their `<!-- id:... -->` markers intact.
2. It emits **edit operations** that reference those block ids —
   `update` / `append` / `supersede` — instead of blind candidates. Only an LLM
   can judge that "personal spending" ≡ the existing "total" block; it expresses
   that judgment by targeting the existing id rather than inventing a new key.
3. A **deterministic apply layer** executes the ops through the *existing*
   `current_value` primitives, so the §3 authority guard, value-equality NOOP,
   and supersede-keeps-history all still fire. **The op is a request, not a
   command** — "the LLM proposes, code disposes." A low-authority `update`
   against a higher-authority block still stages a discrepancy; it never clobbers.

### Rejected alternatives

- **Fixed key schema** — enumerate every allowed key. Rejected: too rigid, kills
  the LLM's inferential flexibility, and the key set grows unbounded across
  files. (User pushback, 2026-06-13.)
- **Vector store / semantic search** — rejected as the wrong tool. It is a
  *read* mechanism; our problem is *writes*. Memory is tiny (fits in context —
  nothing to retrieve) and carries no provenance/authority model. Even Claude
  Code does not use vectors for this. Deferred only as a possible future
  episodic-recall add-on over old transcripts.

### Decisions within the design

- **Hallucinated / bad `target_id`** (the LLM references a non-existent block):
  **append as a new block** (user's call, 2026-06-15). Lower-friction than
  staging to `working/` for review; the value-equality NOOP + dedup guard
  mitigate the case where the id was merely mistyped against an identical value.

### Consequences

- Closes #2 and #6 (the extractor reconciles against what already exists).
- Cost: existing memory now rides in the extractor prompt on every session
  close (acceptable — memory is small; measured after the de-blind slice).
- Risk: the frontmatter stripper must **not** remove `<!-- id:... -->` comments,
  or the extractor loses its targeting anchor. Guarded by an explicit test.

### Invariants preserved (unchanged from §1–§11)

Cross-member isolation (writer = active member; other-member facts → `working/`),
source-authority precedence, the four update modes
(append / current-value / dated-log / narrative), and idempotency via `dedup_id`.

### Build sequence

`M0` this ADR + id-premise verification → `M1` prompt-tightening (also closes the
silent-extraction-loss watch-point) ‖ `M2` staleness caveats → `M3` de-blind the
extractor → `M4` edit-op schema + apply layer (the core rewrite; closes #2/#6) →
`M5` promote stranded family members (#7).
