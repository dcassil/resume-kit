---
id: enforced-human-in-the-loop-edit
level: initiative
title: "Enforced human-in-the-loop edit loop + truth semantics & feedback surfaces"
short_code: "RIT-I-0015"
created_at: 2026-08-05T14:55:06.978119+00:00
updated_at: 2026-08-05T14:55:06.978119+00:00
parent: RIT-V-0001
blocked_by: [RIT-I-0014]
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: L
strategy_id: NULL
initiative_id: enforced-human-in-the-loop-edit
---

# Enforced human-in-the-loop edit loop + truth semantics & feedback surfaces Initiative

## Context **[REQUIRED]**

A real end-to-end tailoring run (phase 2: improve → verify → export) exposed that the
**edit/improve phase has no enforced human-in-the-loop UX**, even though the skills describe one.
The deterministic gates that DO exist behaved beautifully — `identify-gaps`, `match`, `build-evidence`,
`validate-truth`, and `export` were "rock-solid" and `validate-truth` "caught every unsupported
addition and forced me to justify each with evidence." The failure was everywhere the plugin relies on
skill prose instead of code:

- **The acceptance loop is prose, not a gate.** `inject-keywords` says "per-change human acceptance,"
  but nothing enforces it. The test agent hand-edited the working JSON in bulk and substituted
  fact-clarification questions for change-approval — and the plugin never objected. The whole
  present-diff → accept/modify/reject → log → next loop has to be *assembled* by the agent from three
  separate agent-only skills (`inject-keywords`, `rank-edits`, `log-edit-feedback`), so it is trivially
  skipped.
- **No orchestrator / mode prompt.** Nothing asks "interactive vs review-at-end vs auto" up front, and
  nothing ties the loop steps together. `resume-workflow` sequences the phases but leaves the edit loop
  unowned and preference learning "optional."
- **The learning loop got zero records.** `rank-edits` and `log-edit-feedback` have **no CLI/MCP/API/
  facade surface** (their own docs say so; `REGISTRY` has no feedback capabilities). Because they are
  agent-only, they were the easiest part to silently drop — the deterministic feedback engine
  (`packages/feedback`) received nothing from the session.
- **The "why" taxonomy is free-text.** `EditFeedback.rejection_reason: str | None` has no enum, so the
  fabrication / grammar / formatting / not-my-voice signal the ranker wants is unstructured.
- **`validate-truth` cries wolf.** A new-but-true skill token came back `CONTRADICTED` at confidence 1.0
  when it merely meant "not in the evidence base yet." The schema already distinguishes `UNSUPPORTED`
  from `CONTRADICTED`, but the classifier's `_fabricated_values()` reconstructs a "master" resume from
  evidence and treats any skill/cert/company **absent** from it as fabricated → `CONTRADICTED`.
  Conflating absence with conflict makes the strongest gate untrustworthy.
- **No first-class user-confirmation.** Recording the user's verbal "yes, that's true" meant the agent
  hand-writing `CandidateEvidence` JSON. There is an `approved_claims` input path in engine/facade/MCP/
  API, but it is inputs-only (never persisted) and the CLI `build-evidence --approved-claims` documented
  in the skill does not actually exist — a parity bug.

Root cause (confirmed by an independent codex review): the human-in-the-loop editing UX is *designed in
prose but not wired as an enforced flow*. It lives as agent-only skills with no orchestrator, no mode
prompt, no hard write gate, and no standardized reason enum — precisely why the tester could bypass it
without the plugin objecting.

This initiative is scoped to the **edit → verify → export** phase and is intentionally distinct from
[[RIT-I-0014]] (the deterministic **ingest** boundary). It depends on RIT-I-0014's code-owned
`config.json` state contract (RIT-T-0091) for persisting session/evidence/preference state.

### Codex-surfaced gaps beyond the tester's list
- `log-edit-feedback` claims it stores a `PreferencePair`, but no persistence path exists — only
  `EditFeedback` JSONL is written (`packages/feedback/log.py`).
- `align-terminology` computes `truth_passed` but does not reject/revert on truth failure — it reports,
  it does not gate (`packages/alignment/accept.py`).
- `rank-edits` says to honor `alias_file`, but `FeatureContext` has no alias file and candidate truth
  validation is synonym-unaware, so a truthful terminology alias can be falsely hard-blocked
  (`packages/feedback/features.py`).

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Make the edit loop a **code-owned, hard-gated session**: a single orchestrated flow that asks for a
  mode (`interactive` / `review-at-end` / `auto`) up front, and where applying any change **requires**
  a logged accept/modify/reject decision. Unlogged bulk writes to the working resume are refused.
- Correct `validate-truth` semantics so `CONTRADICTED` means *conflicts with evidence* and `UNSUPPORTED`
  means *absent from evidence*; add a machine-readable `reason_code` so gates can distinguish
  "needs evidence" from "contradiction."
- Give the deterministic feedback/learning engine real surfaces: `record-edit-feedback`,
  `rank-edit-candidates`, `refresh-preferences` across facade + CLI + MCP + API with parity tests, so
  the loop actually feeds the learner.
- Standardize the rejection-reason taxonomy as an enum (with free-text `reason_note` retained) that the
  loop offers on every reject/modify.
- Make user-confirmation first-class: `add-evidence --confirmed` deterministically creates and persists
  `user_confirmed` `CandidateEvidence`, and fix the `build-evidence --approved-claims` CLI parity bug.
- Close the codex-surfaced correctness gaps (PreferencePair persistence, `align-terminology` truth
  hard-gate, synonym-aware candidate truth validation).

**Non-Goals:**
- **Not** re-touching the ingest pipeline owned by [[RIT-I-0014]] (extract-text / validate-faithfulness /
  init / set-active). This initiative consumes RIT-T-0091's config contract but does not modify it beyond
  additive session/evidence/preference keys.
- **Not** introducing any new LLM/provider dependency or network call in a deterministic command. The
  interpretation/authoring of edit *content* stays an agent step; everything around it becomes
  deterministic code.
- **Not** replacing the agent's judgment in triage/authoring — the gate constrains *how* changes land,
  not *what* the agent proposes.
- **Not** a full ML ranker — the heuristic feedback engine stays deterministic and transparent.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- **Functional Requirements**
  - REQ-001: A code-owned **edit session** owns the loop: open session → for each candidate change,
    present original vs proposed diff → capture accept / accept_modified / reject / undo + reason_code →
    append an `EditFeedback` record → apply only accepted/modified changes to the working resume →
    re-run truth validation → report. The session is the only sanctioned write path to the working
    resume during improve.
  - REQ-002: The session asks for a **mode** at start — `interactive` (per-change prompt), `review_at_end`
    (batch, then confirm each before commit), `auto` (apply only fully-supported, non-fabricating changes;
    defer anything requiring judgment) — and records the chosen mode.
  - REQ-003: **Hard write gate** — a change cannot be committed to the working resume unless a
    corresponding decision has been logged for it. Attempting to persist unlogged edits fails loudly with
    a machine-readable error naming the offending change(s).
  - REQ-004: `validate-truth` classifies a skill/cert/company **absent** from evidence as `UNSUPPORTED`
    (not `CONTRADICTED`); `CONTRADICTED` is reserved for structural-invariant violations and evidence
    that actively refutes the claim. `ClaimProvenance` gains a `reason_code`
    (`missing_evidence` / `structural_conflict` / `refuted_by_evidence` / `unknown_skill`) and
    `TruthReport` summaries distinguish "needs evidence" from "contradiction."
  - REQ-005: Candidate truth validation is **synonym-aware** — an `alias_file` threads into
    `FeatureContext`/validation so a truthful terminology alias is not falsely hard-blocked.
  - REQ-006: `EditFeedback` gains an `EditFeedbackReasonCode` enum (`fabrication`, `unsupported`,
    `grammar`, `formatting`, `not_my_voice`, `too_verbose`, `too_vague`, `wrong_emphasis`, `duplicate`,
    `other`) plus free-text `reason_note`; existing free-text `rejection_reason` remains loadable
    (backward-compatible).
  - REQ-007: Feedback/learning capabilities are surfaced across facade + CLI + MCP + API with parity:
    `record-edit-feedback`, `rank-edit-candidates`, `refresh-preferences`. `PreferencePair` records are
    actually persisted.
  - REQ-008: `add-evidence --confirmed` deterministically creates and persists `user_confirmed`
    `CandidateEvidence` (project evidence file; optional `active_evidence` pointer) across facade + CLI +
    MCP + API; CLI `build-evidence --approved-claims` parity bug is fixed.
  - REQ-009: `align-terminology` becomes a truth **hard-gate** — a suggestion that fails truth validation
    is rejected/reverted, not merely reported.
- **Non-Functional Requirements**
  - NFR-001: Every new capability follows the existing cross-surface parity norm (facade capability +
    CLI + MCP + API where applicable) with parity tests, consistent with prior phases.
  - NFR-002: All new logic is deterministic and offline — no clock reads inside models (caller-supplied
    timestamps), no network, no LLM in any new command.
  - NFR-003: Schema changes are backward-compatible: existing `edit-feedback.jsonl`, `config.json`, and
    `TruthReport` consumers keep working; new fields are optional/defaulted.

## Architecture **[CONDITIONAL: Technically Complex Initiative]**

### Overview
The edit phase is re-modeled from "three agent-only skills the agent stitches together" into a
**code-owned edit-session spine** with the agent confined to proposing/authoring change *content*:

```
resume-workflow (improve step)
  → [CLI/facade] open edit-session (mode: interactive | review_at_end | auto)     deterministic
  → loop over candidate changes:
      → [AGENT]  propose/author change content                                     semantic
      → [CLI/facade] rank-edit-candidates (heuristic ranker over feedback engine)  deterministic
      → [HUMAN]  accept / accept_modified / reject / undo  + reason_code           gate decision
      → [CLI/facade] record-edit-feedback (append EditFeedback + PreferencePair)   deterministic
      → [CLI/facade] apply accepted change to working resume  (HARD WRITE GATE)    deterministic
      → [CLI/facade] validate-truth (corrected semantics, synonym-aware)           deterministic gate
  → [CLI/facade] refresh-preferences                                               deterministic
  → export (existing)
```

The CLI/facade stays pure deterministic transport; the loop orchestration and the hard write gate live
in code, not skill prose. `add-evidence --confirmed` is a side-channel the loop calls when the human
attests to a new-but-true claim, converting a verbal "yes" into persisted `user_confirmed` evidence that
subsequent `validate-truth` runs will honor.

### Component impact
- **Schemas** (`packages/schemas`): `EditFeedbackReasonCode` enum + `reason_note`; `ClaimProvenance.reason_code`
  + `TruthReport` summary fields; an `EditSession` result/state model.
- **Truth engine** (`packages/evidence/truth.py`): reclassify absent-vs-conflict; add reason codes;
  thread `alias_file`/synonym awareness through `_classify`/`_fabricated_values`.
- **Feedback engine** (`packages/feedback`): `PreferencePair` persistence; expose ranker + log via facade.
- **Alignment** (`packages/alignment/accept.py`): make `align-terminology` reject on truth failure.
- **Facade + CLI + MCP + API**: new capabilities (edit-session, record-edit-feedback,
  rank-edit-candidates, refresh-preferences, add-evidence --confirmed) + `build-evidence --approved-claims`
  CLI fix + parity tests.
- **Skills**: rewrite `inject-keywords`, `rank-edits`, `log-edit-feedback`, `resume-workflow` onto the
  orchestrator + gate + enum; an ADR captures the session/gate design.

### Sequence (hard-gate happy path + bypass rejection)
1. Skill opens an edit session with a chosen mode; session state persisted under `resume-kit/`.
2. Agent proposes a change; ranker scores it; human decides with a reason_code; decision is logged.
3. Apply step verifies a logged decision exists for the change → writes to working resume → re-validates
   truth. If a change is presented for commit **without** a logged decision, the write gate refuses with
   a machine-readable error.

## Detailed Design **[REQUIRED]**

See the decomposed tasks for per-surface design. Design invariants:
- The **hard write gate** is authoritative: no working-resume mutation during improve without a matching
  logged decision. Skill prose is retained only as guidance for the agent's authoring step.
- Truth `CONTRADICTED` vs `UNSUPPORTED` semantics are fixed at the engine and reflected in every surface
  and in the ranker's `unsupported_claim_risk` signal.
- The orchestrator's design is captured in an **ADR** before implementation (this piece is the riskiest,
  most load-bearing, and cross-surface — a wrong contract creates compounding rework).
- Resumes are the primary subject; terminology alignment shares the same truth-gate discipline.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

### Unit Testing
- **Strategy**: Table-driven truth-semantics tests — absent skill → `UNSUPPORTED` + `missing_evidence`;
  refuting evidence → `CONTRADICTED` + `refuted_by_evidence`; structural drop → `CONTRADICTED` +
  `structural_conflict`; synonym alias of a supported term → not hard-blocked. Reason-enum
  backward-compat load of legacy free-text records. Feedback surface unit tests (append + rank +
  preference persistence). Edit-session gate: applying an unlogged change raises; applying a logged
  accepted change writes.
- **Tools**: existing pytest setup.

### Integration Testing
- **Strategy**: End-to-end edit session over a real resume/job fixture exercising all three modes;
  proving (a) the hard gate refuses a bulk unlogged write, (b) a per-change accept/modify/reject loop
  writes only logged changes and feeds the learner, (c) `add-evidence --confirmed` lets a new-but-true
  skill pass `validate-truth` as `USER_CONFIRMED` rather than `CONTRADICTED`, (d) export still runs clean.
- **Data Management**: reuse existing resume/job fixtures; add a small synthetic evidence set.

### Test Selection
Prioritize (1) truth semantics (highest trust impact), (2) the hard write gate, then feedback/evidence
surfaces and parity, then skill-doc coherence.

## Alternatives Considered **[REQUIRED]**

- **Soft gate + warning (offer the orchestrator, still allow direct edits with a loud warning).**
  Rejected by explicit decision: the tester bypassed a prose instruction without friction, so only a
  hard gate that refuses unlogged writes guarantees the bypass cannot recur. A warning is still prose.
- **Add more top-level `ProvenanceStatus` values (e.g. `UNVERIFIED`) instead of a reason_code.**
  Rejected: proliferating statuses churns every consumer and the schema already has `UNSUPPORTED`. A
  `reason_code` sub-classification is lower-blast-radius and richer.
- **Keep feedback skills agent-only and just tighten the prose.** Rejected: the session proved
  agent-only human-in-loop steps are the first thing dropped under pressure; deterministic surfaces are
  what made the ingest/validate side reliable, so the learning loop needs the same treatment.
- **One monolithic "edit orchestrator" task.** Rejected (per decision): the orchestrator is split into a
  design/ADR task and an implementation task because it is the riskiest, most cross-surface piece and a
  wrong contract compounds across the skill rewrites and every surface.

## Implementation Plan **[REQUIRED]**

Sequenced after [[RIT-I-0014]] lands (reuses RIT-T-0091's config contract). Decomposition:

1. **RIT-T-0095** — Truth-semantics correctness: `CONTRADICTED` vs `UNSUPPORTED`, `reason_code`,
   synonym-aware candidate validation, `align-terminology` truth hard-gate. *(opus + high)*
2. **RIT-T-0096** — `EditFeedbackReasonCode` enum + `reason_note` + `PreferencePair` persistence
   (backward-compatible schema). *(opus + low)*
3. **RIT-T-0097** — Feedback & evidence cross-surface capabilities: `record-edit-feedback`,
   `rank-edit-candidates`, `refresh-preferences`, `add-evidence --confirmed`, fix
   `build-evidence --approved-claims` parity. *(opus + high)*
4. **RIT-T-0098** — ADR + design for the code-owned edit-session orchestrator and hard write gate
   (session model, mode contract, gate semantics, cross-surface shape). *(opus + high)*
5. **RIT-T-0099** — Implement the edit-session orchestrator + hard write gate across facade + CLI +
   MCP + API with parity tests. *(opus + high)*
6. **RIT-T-0100** — Rewire skills (`inject-keywords`, `rank-edits`, `log-edit-feedback`,
   `resume-workflow`) onto the orchestrator + gate + reason enum. *(opus + medium)*
7. **RIT-T-0101** — End-to-end integration test + README reconcile + version bump. *(opus + medium)*
