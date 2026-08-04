---
id: phase-4-controlled-alignment
level: initiative
title: "Phase 4 — Controlled Alignment"
short_code: "RIT-I-0005"
created_at: 2026-08-04T04:04:53+00:00
updated_at: 2026-08-04T04:11:32.410562+00:00
parent: RIT-V-0001
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/active"


exit_criteria_met: false
estimated_complexity: XL
strategy_id: NULL
initiative_id: phase-4-controlled-alignment
---

# Phase 4 — Controlled Alignment Initiative

## Context **[REQUIRED]**

Phases 0–3 are complete and pushed. The engine now has canonical schemas (`packages/schemas`),
core contracts (`packages/core`: provider Protocols, `InterfaceResponse`, warnings/provenance,
in-memory fakes), deterministic parsing (`packages/document-parser`), and deterministic analysis
(`packages/matching`, `packages/ats`, `packages/job-parser`). What is missing is the heart of the
product's differentiation: **controlled resume modification** — taking a resume + a job + candidate
evidence and producing a *verified, provenance-tracked, freedom-bounded* set of changes that can
never fabricate facts.

Phase 4 builds the alignment subsystem: the diff apply/verify engine, a generalized freedom-aware
allowed-path policy, the freedom 0–10 model, candidate evidence, claim provenance, truth validation,
and the human-in-the-loop review controller. The central invariant (vision "Freedom Model and Human
Review" + Guarantees): **the LLM never directly writes the final document** — any LLM-proposed change
must pass through the deterministic policy gate, application/verification engine, and truth-validation
before it can appear in an output resume.

**The schema substrate already largely exists** from Phase 1, so Phase 4 is mostly *engine* work over
existing models — new schemas should be minimal:
- `change.py`: `ChangeProposal` (upstream `ResumeChange`, with original-value verification field),
  `Diff`, `ResumeDiffSummary`, `ChangeSet`.
- `evidence.py`: `CandidateEvidence`, `EvidenceKind`.
- `provenance.py`: `ClaimProvenance`, `ProvenanceStatus` (verified/supported/partially-supported/
  user-confirmed/ambiguous/unsupported/contradicted).
Only genuinely missing result types (a freedom policy decision/rejection record, an alignment result
envelope, a truth-validation report, a human-review session/decision model, a skill-target plan
result) should be added to `schemas`, minimally and centrally — never duplicated per package.

Grounding from `references/reuse-inventory.md` (paths relative to `upstream/apps/backend/app/`,
pinned SHA `116f9cc`). NOTE the critical landmine: **`improver.py` is a ~1500-line mega-module** that
mixes path policy, diff apply, diff compute, structural verification, skill-target gating, injection
sanitizing, and LLM generation. Phase 4 **decomposes it along clean boundaries** into `policy`,
`alignment`, and `evidence`:

- **Extract — diff application engine** `apply_diffs` (`improver.py:226`) with `_ALLOWED_PATH_PATTERNS:80`,
  `_BLOCKED_PATH_PREFIXES:94`, `_BLOCKED_FIELD_NAMES:101`, `_is_path_allowed:118`, `_is_path_blocked:123`.
  Gate1 allowed-whitelist, Gate2 blocked-path, path-found, original-match, action validity → returns
  (result, applied, rejected). Pure code, depends only on `app.schemas.models`. **Split**: path-policy
  → `policy`; application → `alignment`. Tests: `tests/unit/test_apply_diffs.py`.
- **Extract — blocked fields** `_BLOCKED_FIELD_NAMES` frozenset (company/employer/title/name/date/
  institution/location) + `_BLOCKED_PATH_PREFIXES` (`improver.py:94,101`) → generalize into a
  **freedom-aware policy table** in `policy`.
- **Extract — original-value verification** `_verify_original_matches(actual, expected)`
  (`improver.py:215`) — rejects a change whose stated original ≠ actual resume value. → `alignment`.
- **Extract — skill-addition gates** `_build_allowed_skill_target_keys`/`verify_skill_target_plan`
  (`improver.py:376,709,754`; `refiner.py:290`) — reject unverified/duplicate skills; deterministic.
  Verifier → `policy`/`alignment`; the *planner* (`generate_skill_target_plan`, LLM) is Adapt behind
  the provider Protocol. Tests: `test_verify_diffs.py`, `service/test_improver.py`.
- **Extract — malformed/unsupported change rejection** (`improver.py:289–408`) + **omitted-content
  preservation** (reorder salvage, `_preserve_personal_info`, `improver.py:335–363`) → `alignment`.
- **Extract — structural truthfulness verifier** `verify_diff_result` (`improver.py:430`) — warns on
  dropped work/education/projects, company/title/institution changes, word-count explosion, invented
  %/$ metrics. Pure `re`. → `evidence`/`alignment`. Tests: `test_verify_diffs.py` (18 asserts).
- **Reuse — structural eval scorers** `sections_preserved`, `no_fabricated_employers`,
  `personal_info_unchanged` (`tests/evals/scorers.py:100,117,138`) — port as reusable truth-validation
  predicates in `evidence` (the `jd_keywords_present`/`is_valid_resume` pair already landed in Phase 3).
- **Extract — structured diff computation** `calculate_resume_diff` (`improver.py:1224`) — strict
  field-level diff (skills add/remove case-insensitive order-ignored, certs, summary, experience/
  education/project entries) → `alignment`. Tests: `test_resume_diff.py` (~25 tests). (Phase 3's
  `compare_versions` is score-delta; this is content-diff — distinct.)
- **Extract — fabrication detection** `validate_master_alignment`/`fix_alignment_violations`
  (`refiner.py:290,591`) — flag/strip skills/certs/companies absent from master (allowing verified JD
  skills) → `evidence` (truth engine seed). Tests: `test_refiner.py`.
- **Reuse — prompt-injection sanitizer** `_sanitize_user_input` (`improver.py:48`, `_INJECTION_PATTERNS:29`)
  → `policy`, reusable as-is (deterministic security guard).
- **Adapt — LLM generation** `generate_resume_diffs`/`improve_resume`/`generate_improvements`
  (`improver.py:506,910,1474`) and `generate_skill_target_plan` (`improver.py:839`), plus prompts
  `IMPROVE_RESUME_PROMPT_*`, `DIFF_IMPROVE_PROMPT`, `KEYWORD_INJECTION_PROMPT`, `SKILL_TARGET_PLAN_PROMPT`,
  and `CRITICAL_TRUTHFULNESS_RULES*` (`templates.py`, `refinement.py`). Inverted behind
  `core.StructuredCompletionProvider`; **generation only proposes** `ChangeProposal`s — policy +
  apply + verify + truth-validate are the gates the proposal must clear. Adapt prompts for freedom levels.

Vision Phase 4 explicitly requires: extract diff apply/verify engine; generalize allowed-path policy;
implement `freedom: 0-10`; implement verified skill targets; add candidate evidence + claim
provenance; implement human-in-the-loop review; implement `validate-resume-truth`; and ensure the LLM
never writes the final document without passing policy + verification gates. The CLI/MCP/API
*interfaces* for `align-resume`/`validate-resume-truth`/`build-candidate-evidence` are **Phase 5** —
Phase 4 delivers the reusable core engine + result models + the orchestration function, not the
command wrappers. Every ported/adapted unit carries a modified-source marker + an
`references/attribution.md` row (SHA `116f9cc`) and characterization tests before behavior change.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Stand up `packages/policy` (`resume_kit_policy`), `packages/alignment` (`resume_kit_alignment`), and
  `packages/evidence` (`resume_kit_evidence`) as `uv`-workspace members depending inward only on
  `resume_kit_schemas` + `resume_kit_core` (and `alignment` may depend on `policy`/`evidence`; keep the
  graph acyclic). Never `app.*`, never a concrete LLM provider.
- **Freedom-aware allowed-path policy** in `policy`: generalize upstream's fixed allowed/blocked gates
  into a graduated **freedom 0–10** policy table (vision "Freedom Model": F0 skills-only correction →
  F10 maximum truthful alignment). A `PolicyDecision`/rejection-reason model records why a change was
  allowed or blocked at a given freedom level. Blocked factual fields (employer/title/date/name/
  institution/location/metrics) are **never** editable regardless of freedom. Includes the reused
  injection sanitizer and truthfulness-rule constants.
- **Diff apply/verify engine** in `alignment`: port `apply_diffs` (allowed/blocked gates via `policy`,
  path-found, original-match verification, action validity, malformed/unsupported rejection,
  omitted-content preservation) → `(applied, rejected)` over a `ChangeSet`; port `calculate_resume_diff`
  (structured content diff); port `verify_diff_result` structural truthfulness verifier. All
  characterization-tested to upstream parity BEFORE any freedom-aware generalization.
- **Verified skill targets** in `policy`/`alignment`: deterministic `verify_skill_target_plan` gate
  (reject unverified/duplicate skills; only verified-JD or evidence-backed skills may be added); the
  LLM planner is provider-injected and its output must clear this gate.
- **Candidate evidence** in `evidence`: `build_candidate_evidence(...)` assembling `CandidateEvidence`
  records from a resume (+ optional approved-claim inputs); the substrate the truth engine classifies
  against.
- **Claim provenance + truth validation** in `evidence`: `validate_resume_truth(resume, evidence)` →
  a truth-validation report classifying each material claim as verified/supported/partially-supported/
  user-confirmed/ambiguous/unsupported/contradicted (`ClaimProvenance`), built on the reused structural
  evaluators + fabrication detection. Deterministic core; LLM semantic classification optional and out
  of scope here.
- **Human-in-the-loop review controller** in `alignment`: a section-by-section controller that, per
  section, exposes current + proposed content, change explanation, evidence for material claims,
  expected score impact, and a decision surface (approve/reject/edit/retry/reduce-freedom/
  increase-freedom/skip) that will not advance until the section is resolved. Delivered as a pure,
  interface-agnostic state machine (`InterfaceResponse` with `requiresHumanInput` + questions) — the
  actual interactive loop is Phase 5. The non-human-in-loop path returns a full diff, provenance,
  warnings, unresolved questions, before/after match score, ATS report, and truth report in one pass.
- **`align_resume(...)` orchestration** in `alignment`: the top-level function wiring
  generation(provider) → policy gate → apply → verify → truth-validate, enforcing the invariant that
  no unsupported claim is emitted and F≥3 automatically runs truth validation (vision guarantee).
- Green toolchain: `ruff`, `mypy --strict`, `pytest` all pass; characterization tests for every ported
  unit; provider-boundary tests use the in-memory fake from `resume_kit_core.testing` (no network).
  Existing 573 tests stay green.

**Non-Goals:**
- CLI/MCP/API/plugin interfaces (Phase 5) and the interactive human-in-loop terminal/tool loop —
  Phase 4 ships the controller *engine*, not its transport.
- Export/PDF/DOCX generation and cover-letter alignment (Phase 6).
- A concrete LiteLLM provider — generation/planning use only the `core` Protocol + fake in tests.
- LLM-based semantic truth classification and LLM reranking — Phase 4 truth validation is deterministic
  and structural; LLM semantic interpretation is a later optional enhancement.
- Persistent approved-claim *storage* (a DB/bank) — Phase 4 accepts approved claims as inputs and
  models them; a durable store is a later concern. Model the type; do not build persistence.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- **Functional:**
  - REQ-401: `packages/policy`, `packages/alignment`, `packages/evidence` are `uv`-workspace members
    importing cleanly; public APIs exported via `__init__`; acyclic dependency graph
    (alignment → policy, evidence, schemas, core).
  - REQ-402: `policy` exposes a freedom 0–10 policy that, given a `ChangeProposal` + freedom level,
    returns a `PolicyDecision` (allow/block + reason). Factual fields are blocked at every level.
    Upstream fixed-gate behavior is reproduced at the equivalent freedom level (characterization-tested).
  - REQ-403: `alignment` applies a `ChangeSet` deterministically: allowed/blocked gates (via `policy`),
    path resolution, original-value verification, action validity, malformed/unsupported rejection,
    omitted-content preservation → `(applied, rejected)`; parity-tested against upstream `apply_diffs`.
  - REQ-404: `alignment` computes a structured content diff (`calculate_resume_diff` parity) and runs
    the structural truthfulness verifier (`verify_diff_result` parity: dropped sections, changed
    employer/title/institution, word-count explosion, invented metrics).
  - REQ-405: skill additions are gated by a deterministic verified-target check; unverified/duplicate
    skills are rejected; only verified-JD or evidence-backed skills may be added.
  - REQ-406: `evidence` builds `CandidateEvidence` from a resume (+ optional approved claims) and
    validates truth → a report of `ClaimProvenance` per material claim across the 7 statuses; no
    `align_resume` output may contain an `unsupported`/`contradicted` claim.
  - REQ-407: `alignment.align_resume(resume, job, evidence, freedom, humanInLoop, provider)` orchestrates
    generation → policy → apply → verify → truth-validate; LLM output is proposal-only and always
    passes the gates; F≥3 forces truth validation; returns an alignment result envelope with diff,
    provenance, warnings, questions, before/after match score, ATS report, truth report.
  - REQ-408: human-in-loop controller is a pure state machine returning `requiresHumanInput` +
    per-section questions and not advancing until the current section is resolved; non-human-in-loop
    returns a complete one-pass proposal with the full report set.
  - REQ-409: any new result models (policy decision, alignment result, truth report, review session/
    decision, skill-target plan) are added to `packages/schemas` minimally and reused.
- **Non-Functional:**
  - NFR-401: `mypy --strict` passes for all three new packages; `ruff` clean; existing 573 tests green.
  - NFR-402: No `app.*` import and no concrete-provider import anywhere in the new packages (enforced by
    per-package import-boundary tests).
  - NFR-403: No network/LLM in any test — generation/planning paths use the fake provider.
  - NFR-404: Every ported/adapted unit has a modified-source marker + an `attribution.md` row (SHA
    `116f9cc`).
  - NFR-405: The LLM-never-writes-the-final-document invariant is covered by an explicit test: a
    fabricating provider proposal is rejected/stripped by the gates and never reaches the output resume.

## Architecture **[CONDITIONAL: Technically Complex Initiative]**

### Overview
Adds the controlled-transformation layer above analysis, decomposing upstream `improver.py`:
```
packages/schemas    — ChangeProposal, Diff, ChangeSet, CandidateEvidence, ClaimProvenance (exist) +
                      minimal new: PolicyDecision, AlignmentResult, TruthReport, ReviewSession/Decision,
                      SkillTargetPlan.
packages/core       — provider Protocols, InterfaceResponse, warnings/provenance (exist).
packages/policy     — NEW. Freedom 0–10 policy table, allowed/blocked-path + blocked-field gates,
                      verified-skill-target check, injection sanitizer, truthfulness-rule constants.
                      Depends on schemas (+ core). No LLM.
packages/evidence   — NEW. build_candidate_evidence, validate_resume_truth, claim-provenance
                      classification, fabrication detection, structural truth predicates. Depends on
                      schemas + core. Deterministic (LLM optional, out of scope).
packages/alignment  — NEW. apply_diffs engine, original-match verify, structured diff compute,
                      verify_diff_result, human-in-loop controller, align_resume orchestration.
                      Depends on schemas + core + policy + evidence + (matching/ats for score impact).
```
The only LLM paths (diff/skill-target generation) are invoked through the injected
`StructuredCompletionProvider` and produce proposals only; every proposal traverses policy → apply →
verify → truth. `alignment` composes `matching`/`ats` for before/after score impact (explicit, acyclic
inward dependency). Package boundaries mirror the vision architecture (policy/alignment/evidence as
distinct packages) and keep the LLM-free guarantees isolated in `policy`/`evidence`.

## Detailed Design **[REQUIRED]**

Follow the vision extraction order per ported unit: locate upstream (done — see Context) → review →
classify (done — reuse inventory) → **port tests / add characterization tests first** → extract behind
clean boundaries → only then generalize (freedom levels). Concretely:
1. Scaffold `policy`, `alignment`, `evidence` (pyproject/py.typed/tests, workspace + schemas/core deps,
   toolchain). Add minimal new schema result types to `schemas`.
2. `policy`: extract `_ALLOWED_PATH_PATTERNS`/`_BLOCKED_PATH_PREFIXES`/`_BLOCKED_FIELD_NAMES` +
   `_is_path_allowed`/`_is_path_blocked` into a path-policy module; characterization-test parity; then
   generalize into a freedom 0–10 table returning `PolicyDecision`. Port `_sanitize_user_input` +
   truthfulness-rule constants. Port `verify_skill_target_plan` verified-target gate.
3. `alignment` (apply): port `apply_diffs` (using `policy` gates) + `_verify_original_matches` + reorder
   salvage / `_preserve_personal_info` + malformed/unsupported rejection → `(applied, rejected)`;
   characterization-test parity with `test_apply_diffs.py`.
4. `alignment` (diff + verify): port `calculate_resume_diff` and `verify_diff_result`;
   characterization-test parity with `test_resume_diff.py` / `test_verify_diffs.py`.
5. `evidence`: port structural eval scorers as truth predicates + `validate_master_alignment`/
   `fix_alignment_violations` fabrication detection; build `build_candidate_evidence` and
   `validate_resume_truth` → provenance report over the 7 statuses.
6. `alignment` (orchestration + controller): `align_resume` wiring generation(provider) → policy →
   apply → verify → truth; human-in-loop state-machine controller returning `requiresHumanInput` +
   section questions; enforce no-unsupported-claim + F≥3-forces-truth invariants. Provider-boundary
   tests via the fake, including the fabricating-provider rejection test (NFR-405).
7. Attribution rows + per-package import-boundary tests + `__init__` exports (late wave).

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- **Characterization tests** for `apply_diffs`, `calculate_resume_diff`, `verify_diff_result`, path
  policy, and skill-target verification — written to pass against current upstream behavior BEFORE any
  freedom-aware generalization (prove-it-fails when logic is broken).
- **Unit tests** for the freedom 0–10 policy table (each level's allow/block boundaries, factual fields
  blocked at every level), evidence building, and truth-validation classification across all 7 statuses.
- **Invariant/adversarial tests:** fabricating provider proposal → rejected by gates, never in output
  (NFR-405); F≥3 auto-runs truth validation; no `unsupported`/`contradicted` claim in any align output;
  blocked factual field edits rejected at freedom 10.
- **Provider-boundary tests** for generation/skill-target planning using the in-memory fake:
  happy path → gated proposals applied; malformed output → warnings + rejection; no-provider → no
  generation (deterministic-only) path still returns a valid (empty-change) result.
- **Human-in-loop controller tests:** state machine emits `requiresHumanInput` + section questions,
  does not advance until resolved; non-human path returns the full one-pass report set.
- All deterministic; no network. Existing 573 tests must stay green. Per-package import-boundary tests
  assert no `app.*`/concrete-provider imports.
- Gate: `uv run ruff check packages tests && uv run mypy packages/core packages/schemas packages/document-parser packages/matching packages/ats packages/job-parser packages/policy packages/evidence packages/alignment && uv run pytest`
  (run `uv sync --all-packages` first — plain `uv sync` skips non-root workspace members).

## Alternatives Considered **[REQUIRED]**

- **One combined `alignment` package holding policy + evidence + apply/verify.** Rejected: the vision's
  package architecture separates policy, alignment, and evidence; combining them re-couples the LLM-free
  guarantees (policy/evidence must be trivially auditable as deterministic) with the orchestration that
  *does* touch the provider. Three focused packages keep the "LLM never writes the final document"
  boundary honest and enable file-disjoint parallel work.
- **Port `improver.py` wholesale, refactor later.** Rejected: it is a ~1500-line mega-module mixing
  policy, apply, compute, verify, skill gating, sanitizing, and LLM generation. Porting it intact drags
  `app.*` coupling and an untestable blob into the clean core; the reuse inventory already identifies
  clean seams. Decompose along those seams under characterization protection.
- **Freedom as a free-form prompt instruction to the LLM.** Rejected: freedom must be a *deterministic
  policy gate*, not a suggestion — the guarantee is that no freedom level (including 10) can fabricate
  facts. A prompt-only freedom model cannot enforce that. Freedom is a policy table the LLM's proposals
  must clear.
- **LLM-based truth validation now.** Rejected: the vision wants deterministic, structural truth
  validation first (dropped sections, changed employers, invented metrics, unverified skills). LLM
  semantic classification is an optional later enhancement and would undermine the no-LLM guarantee.
- **Build persistent approved-claim storage this phase.** Rejected: persistence is out of the toolkit's
  stated scope (job-hunter owns state). Model `CandidateEvidence`/approved claims as inputs; defer any
  durable store.

## Implementation Plan **[REQUIRED]**

Decomposed by a codex agent into file-disjoint tasks (see child tasks). Expected shape:
1. Scaffold `policy`, `alignment`, `evidence` + minimal new schema result types — lands first.
2. `policy`: path-policy extraction + parity, freedom 0–10 table, injection sanitizer, truthfulness
   constants, verified-skill-target gate.
3. `alignment`: `apply_diffs` engine (using policy) + original-match + preservation + rejection — parity.
4. `alignment`: `calculate_resume_diff` + `verify_diff_result` — parity.
5. `evidence`: candidate-evidence build + truth-validation/provenance + fabrication detection.
6. `alignment`: `align_resume` orchestration + human-in-loop controller + provider-boundary/invariant
   tests.
7. Attribution rows + import-boundary tests + `__init__` exports (late wave).
Waves ordered so scaffolding + schema types land first, then `policy` and `evidence` (file-disjoint,
parallel), then `alignment` apply/diff/verify (depends on policy), then `align_resume` orchestration
(depends on policy + evidence + matching/ats), then attribution/exports last.

**Exit criteria:** three packages import cleanly as workspace members; `apply_diffs`,
`calculate_resume_diff`, `verify_diff_result`, path policy, and skill-target verification ported +
characterization-tested to upstream parity; freedom 0–10 policy table implemented with factual fields
blocked at every level; candidate evidence + truth-validation/provenance implemented across the 7
statuses; `align_resume` orchestration enforces the LLM-never-writes-final-document invariant, the
no-unsupported-claim rule, and F≥3-forces-truth; human-in-loop controller is a pure state machine;
every ported unit attributed (SHA `116f9cc`) and marked; no `app.*`/provider imports (boundary tests);
`ruff` + `mypy --strict` + `pytest` all green; existing 573 tests still pass.