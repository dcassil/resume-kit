---
id: perfect-fit-pass-job-aware-budget
level: initiative
title: "Perfect/fit pass: job-aware budget enforcement via ranked, decision-driven trims after tailoring"
short_code: "RIT-I-0021"
created_at: 2026-08-07T18:29:07.699663+00:00
updated_at: 2026-08-08T01:47:00.299168+00:00
parent: RIT-V-0001
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: false
estimated_complexity: L
strategy_id: NULL
initiative_id: perfect-fit-pass-job-aware-budget
---

# Perfect/fit pass: job-aware budget enforcement via ranked, decision-driven trims after tailoring Initiative

## Context **[REQUIRED]**

This is the **third and final initiative** reshaping the resume pipeline (see [[RIT-I-0019]] and [[RIT-I-0020]]). The target pipeline is:

```
original → base → structure → refine → tailored → perfect
```

- **`structure`** — lossless canonicalization ([[RIT-I-0019]]).
- **`refine`** — job-independent wording quality ([[RIT-I-0020]]).
- **`tailored`** — job-specific keyword/terminology edits (existing tailoring skills).
- **`perfect`/`fit`** — *this initiative*: the final, **job-aware** pass that runs **after** a tailored resume exists and makes it *fit* — enforcing budgets (max skills, max experience entries, bullets per role, bullet/summary length, max pages) by **ranked, decision-driven trims**, never silent cuts, then producing the finalized artifact.

The governing principle locked across the pipeline design: *relevance/emphasis/angle → tailored; budgets/caps/trimming → perfect; truth-preserving wording quality → refine.* Every prior stage is deliberately **non-destructive of substantive content** — `structure` moves, `refine` rewords/enriches, `tailored` re-angles. That keeps the richest truthful master intact right up until a specific job is chosen. **`perfect` is the only stage allowed to remove content**, and it may do so **only** by an explicit ranked decision (or an opt-in auto-fit against a default ranking), never silently — because the removals are lossy and job-specific, and doing them earlier risks dropping exactly the keyword/role a target job wants.

Two budget rules are explicitly **handed to this pass by [[RIT-I-0020]]**: `SUMMARY_TOO_LONG` (length budget) and `FOUNDATIONAL_SKILL` (relevance cut) were removed from the `refine` wording pass and their detectors relocated/tagged for reuse here (length) and in tailoring (relevance). This initiative owns the budget half.

**Reuse mandate (explicit, from design discussion).** This pass must **not** invent a new suggest/apply/learn stack. It reuses the existing, proven reusables end to end:
- **Suggest → decide → apply loop:** the [[RIT-I-0015]] **edit-session orchestrator** + hard write gate ([[RIT-A-0001]]) — `open-edit-session` → `session-prompt` → `decide-change` → `reconcile-session` → `commit-session` (facade `open_session`/`prompt_session`/`decide_change`/`reconcile_session`/`commit_session`), with each trim expressed as a `ChangeProposal`.
- **Apply mechanics:** the shared **change-application runbook** ([[RIT-A-0005]] Decision B / [[RIT-T-0124]]) that the `update-*` skills already defer to, and the `align-resume` apply/policy/truth path.
- **Learn loop:** the [[RIT-I-0013]] feedback + preference stack — `record-edit-feedback`, `rank-edit-candidates`, `refresh-preferences` (facade equivalents), and the `learn-change` / `rank-changes` skills — so accepted/rejected trims train future ranking.

The only genuinely new logic is (a) the **budget model** (which lives in the [[RIT-I-0019]] `ResumeShapePolicy` as informational fields, now *enforced* here) and (b) the **job-aware ranking** that turns "over budget by N" into an ordered list of trim `ChangeProposal`s. Everything else is orchestration over existing reusables.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Introduce the final **`perfect`/`fit`** pass in the lineage, taking a **tailored** resume + its **target job** and producing a finalized, budget-conformant artifact (`<name>-<job>-final.json` or equivalent) with a `final`/`perfect` pointer and provenance.
- Enforce the shape-policy **budgets** as real constraints here (max skills, max experience entries, bullets per recent/older job, bullet words, summary words, max pages) — reusing the [[RIT-I-0019]] `ResumeShapePolicy` budget fields that were informational-only pre-job.
- Turn each over-budget condition into **ranked trim candidates** (`ChangeProposal`s), never silent removals: skills, experience entries, and bullets each get a deterministic, **job-weighted** ranking; the lowest-ranked become trim candidates until under budget; summary/bullet over-length become **compression** candidates (claim-gated rewrites, not naive truncation).
- Drive all trims through the **reused suggest→decide→apply loop** (edit-session orchestrator + hard write gate) and record accept/reject through the **reused learn loop** (feedback + preference refresh) so ranking improves over time. Support an opt-in **auto-fit** mode that applies the default ranking without prompting (still logged, still gated).
- Add a **content ledger** posture appropriate to *this* stage: unlike `structure`/`refine`, `dropped_by_explicit_decision` and (in auto-fit) `dropped_by_ranked_budget` are **allowed** ledger reasons here — but every drop is still accounted for, and claim/truth gates still apply to anything rewritten (compressions).
- Add the **render/page hard-gate at export**: estimate pages during `perfect` (warn), and hard-gate at `export`/`resume_export` if the rendered document exceeds `max_pages`, unless the user overrides. Real page count comes from the renderer, not a JSON heuristic.
- Own the two rules handed over by [[RIT-I-0020]]: consume the relocated `SUMMARY_TOO_LONG` as a **length-budget** finding; implement the job-aware **relevance** trim that `FOUNDATIONAL_SKILL`'s intent described (drop-too-basic-skill, now job-weighted).
- Expose across facade/CLI/MCP/API + a `perfect`/`fit` plugin skill, wired into `resume-workflow` as the final step after tailoring and before/at export.

**Non-Goals:**
- **Job-independent work of any kind** — structure, wording quality, canonicalization — owned by `structure`/`refine`; unchanged. `perfect` never re-canonicalizes or re-words for quality; it only fits.
- **Job-specific *content* generation** (keyword injection, terminology mirroring, new bullets) — owned by the `tailored` pass. `perfect` selects/compresses existing tailored content; it does not add new claims.
- **Mutating the master lineage.** `perfect` operates on a **job-specific tailored projection** and writes a job-specific final artifact. It never edits `structure`/`refine`/`base`/`original` — consistent with the canonical model's Rule 8 ("canonical resume ≠ submitted resume").
- **Building a new orchestrator, apply engine, or feedback system.** Reuse [[RIT-I-0015]]/[[RIT-A-0001]], [[RIT-A-0005]]/[[RIT-T-0124]], and [[RIT-I-0013]] as-is. New code is limited to the budget-enforcement + ranking layer and the export page-gate.
- **Fabrication.** Compressions are claim-gated truthful rewrites; trims remove existing content by decision. No new metrics/skills/claims are ever introduced.

## Requirements **[REQUIRED]**

### User Requirements
- **User Characteristics**: Same population as prior initiatives — job seeker via the conversational skill surface + automation via CLI/MCP. Users make keep/drop/compress decisions when prompted; power users may opt into auto-fit.
- **System Functionality**: After a `tailored` resume exists for a specific job, the user runs `perfect`. The system reports every over-budget condition, presents **ranked** trim/compression candidates (job-weighted, lowest-value first), and walks the user through keep/drop/compress decisions via the existing edit-session loop. Nothing is removed without a decision (or an explicit auto-fit opt-in). On completion it writes the finalized job-specific artifact; export hard-gates on page count.
- **User Interfaces**: A `perfect`/`fit` plugin skill (conversational, reusing the edit-session decision UX) + CLI/MCP/API parity. Interactive mode = ranked candidates + per-item decisions; auto-fit mode = apply default ranking to budget, logged and gated. The export page-gate surfaces a clear over-length blocker with an override.

### System Requirements
- **Functional Requirements**:
  - REQ-001: **`build_perfect`/`fit` capability.** Add a facade capability `build_perfect(root, *, job, decisions=None, auto_fit=False) -> BuildPerfectResult` that resolves the **tailored** resume for a given job (+ the active job description), runs budget enforcement, drives trims through the edit-session orchestrator, and writes the finalized job-specific artifact + pointer/provenance. Mirrors the `build_*` shape of prior passes.
  - REQ-002: **Budget enforcement from the shape policy.** Enforce the [[RIT-I-0019]] `ResumeShapePolicy` budget fields (skills_count, experience_entries, recent/older job bullets, bullet_words, summary_words, max_pages) as real constraints here. Project-overridable. Each violated budget yields findings that map to ranked candidates.
  - REQ-003: **Job-aware ranking (the new logic).** Deterministic ranking modules for skills, experience entries, and bullets, **weighted by the target job** (reuse `resume_kit_matching/keywords.py` + the project alias index / [[RIT-I-0009]] alias grow). Skills: keep those matched in the job + used in experience/summary; drop duplicates/umbrella/soft-skill/foundational items first. Jobs: keep recent/senior/relevant; compress older before removing; preserve continuity unless the user approves removal. Bullets: keep quantified impact + architecture/leadership/scope; drop redundant/tool-only first. **Ties defer** to a decision — never a silent pick.
  - REQ-004: **Trims as `ChangeProposal`s through the reused loop.** Each trim/compression is a `ChangeProposal` fed through the [[RIT-I-0015]] edit-session orchestrator (`open_session`/`prompt_session`/`decide_change`/`reconcile_session`/`commit_session`) behind the [[RIT-A-0001]] hard write gate, applied via the [[RIT-A-0005]]/[[RIT-T-0124]] shared change-application runbook. `perfect` does **not** implement its own apply path.
  - REQ-005: **Learn loop reuse.** Accept/reject decisions are recorded via `record-edit-feedback` and fold into `refresh-preferences` / `rank-edit-candidates` ([[RIT-I-0013]]), and the `learn-change`/`rank-changes` skills, so the trim ranking improves from user behavior. `perfect` does **not** implement its own feedback store.
  - REQ-006: **Stage-appropriate content ledger.** Reuse the [[RIT-I-0019]] `ContentLedger` shape but with an expanded allowed-reason set for this stage: `present_after | moved | deduped | dropped_by_explicit_decision | dropped_by_ranked_budget | compressed`. A gate asserts every removed token is accounted for by a *decision* (interactive) or the *ranked-budget* reason (auto-fit only) — never an unexplained loss.
  - REQ-007: **Compression, not truncation.** Over-length summary/bullets produce claim-gated **rewrite** candidates that shorten while preserving claims and meaning — routed through the same truth/claim gates as `refine`. Naive string truncation is prohibited.
  - REQ-008: **Auto-fit mode.** An opt-in mode applies the default job-weighted ranking to bring the resume under budget without per-item prompts. Still logged (feedback), still gated (truth/claim/ledger), and it `log()`s exactly what it dropped (no silent truncation — align with the "no silent caps" discipline).
  - REQ-009: **Export page hard-gate.** Estimate pages during `perfect` (informational warning). At `export`/`resume_export`, hard-gate if the **rendered** page count exceeds `max_pages`, with a user override flag. Real measurement from the renderer (`resume_kit_export`), not a JSON heuristic.
  - REQ-010: **Consume handoffs from [[RIT-I-0020]].** Implement the relocated `SUMMARY_TOO_LONG` as the summary length-budget path, and the job-aware relevance trim that realizes `FOUNDATIONAL_SKILL`'s intent (drop-too-basic-skill weighted by the job).
  - REQ-011: **Lineage + provenance.** Add a `final`/`perfect` job-specific pointer keyed by job (a tailored resume is per-job, so the final is per-job) with provenance back to the tailored source and the job. Never mutates master lineage (`structure`/`refine`/`base`/`original`).
  - REQ-012: **Surfaces + skill + workflow.** Facade + CLI (`resume-tool fit`/`perfect`) + MCP (`resume_build_perfect`) + API with cross-surface parity; a `perfect`/`fit` skill reusing the edit-session decision UX; `resume-workflow` updated so `perfect` is the final step after tailoring, and export enforces the page-gate.
  - REQ-013: **E2E integration test.** Real-fixture `tailored → perfect`: an over-budget tailored resume (too many skills/roles/bullets, over-length summary) produces ranked candidates, a simulated decision path brings it under budget with full ledger accounting, compressions pass truth/claim gates, and the export page-gate blocks an over-length render and passes after fit.
- **Non-Functional Requirements**:
  - NFR-001 (Determinism): Ranking is deterministic and reproducible for a fixed (resume, job, policy); ties defer rather than coin-flip. Any LLM assist (e.g. compression phrasing) is confined and separable, consistent with the existing analyzer/align contract.
  - NFR-002 (Truth/Accountability): No fabricated content; compressions pass truth/claim gates; every removal is decision- or ranked-budget-accounted in the ledger. Hard gates per [[RIT-A-0001]].
  - NFR-003 (Non-mutation of master): `perfect` writes only job-specific finals; master lineage is never edited (canonical Rule 8).
  - NFR-004 (Reuse): No new orchestrator/apply/feedback stacks — measured by tests asserting `perfect` routes through the existing edit-session + change-application + feedback capabilities.
  - NFR-005 (Surface parity): Identical behavior across facade/CLI/MCP/API for the same (resume, job, policy), enforced by parity tests.

## Use Cases **[REQUIRED]**

### Use Case 1: Fit a bloated tailored resume to two pages (interactive)
- **Actor**: Job seeker with a `tailored` resume for a specific job that is 3 pages with 40 skills and 9 roles.
- **Scenario**: User runs `perfect`. The system reports over-budget on skills (40 > 32), experience entries (9 > 6), and estimated pages (3 > 2). It presents **ranked** candidates: lowest-job-relevance skills first (foundational/soft/umbrella, none matched in the job), oldest low-relevance roles proposed for **compression** (fewer bullets) before removal, over-length bullets proposed as claim-gated compressions. Each is a `ChangeProposal` surfaced through `session-prompt`; the user accepts/rejects via `decide-change`. Decisions are logged via `record-edit-feedback`.
- **Expected Outcome**: A finalized job-specific artifact under budget; full ledger accounting (every drop = a decision); compressions passed truth/claim gates; the export page-gate now passes; preferences updated so next time the ranking reflects the user's choices.

### Use Case 2: Auto-fit for an automation run
- **Actor**: The job-hunter bridge finalizing many tailored resumes.
- **Scenario**: Calls `build_perfect(..., auto_fit=True)`. The default job-weighted ranking trims to budget without prompts; every drop is logged (`dropped_by_ranked_budget`) and gated; compressions pass truth/claim gates; anything ambiguous/tied is **deferred** (left for a human) rather than auto-cut.
- **Expected Outcome**: Under-budget finals produced unattended, with a logged, auditable trim list; tied/ambiguous cases surfaced for human resolution; no silent truncation.

### Use Case 3: Export page-gate blocks an over-length render
- **Actor**: Job seeker exporting a finalized resume.
- **Scenario**: Even after JSON-level budgets pass, the rendered PDF is 2.3 pages against a `max_pages: 2`. `export` hard-gates with a clear message and an override option; the user either overrides or returns to `perfect` for one more compression pass.
- **Expected Outcome**: No accidental over-length submission; the page limit is enforced against the *real* render, not a guess.

## Architecture **[REQUIRED]**

### Overview
Layered as before: a new budget-enforcement + ranking layer in `resume-kit-scoring` (consuming the [[RIT-I-0019]] `ResumeShapePolicy` budgets and the `resume-kit-matching` job index), orchestrated by a `build_perfect` facade capability that **delegates suggest/apply/learn to existing reusables**, thin CLI/MCP/API adapters, a `perfect`/`fit` skill, and a page-gate in `resume-kit-export`. The only new engines are the ranking modules and the budget enforcer; the orchestration, apply, and feedback are entirely reused.

### Component Diagram (described)
- **`resume-kit-scoring` (new modules)**: `budget_enforce` (policy budgets → violations), `rank_skills`/`rank_experience`/`rank_bullets` (job-weighted deterministic rankers → ordered trim candidates), `compress` (claim-gated length rewrites). Reuse the `ContentLedger` with the expanded reason set.
- **Reused orchestration ([[RIT-I-0015]]/[[RIT-A-0001]])**: `open_session`/`prompt_session`/`decide_change`/`reconcile_session`/`commit_session`; each trim/compression is a `ChangeProposal`. **Not reimplemented.**
- **Reused apply ([[RIT-A-0005]]/[[RIT-T-0124]])**: the shared change-application runbook + `align-resume` apply/policy/truth path.
- **Reused learn ([[RIT-I-0013]])**: `record-edit-feedback` → `refresh-preferences` / `rank-edit-candidates`; `learn-change`/`rank-changes` skills.
- **`resume-kit-export`**: page-count hard-gate at render, with override.
- **`resume-kit-facade`**: `build_perfect`; job-specific `final` pointer + provenance; never touches master lineage.
- **Surfaces**: facade + CLI/MCP/API + `perfect`/`fit` skill; `resume-workflow` final step.

### Sequence (described)
`tailored` exists for job J → `build_perfect(job=J)` → `budget_enforce(tailored, policy)` yields violations → job-weighted rankers produce ordered trim/compression `ChangeProposal`s → `open_session` + `prompt_session`/`decide_change` (or auto-fit applies default ranking) → each apply via the shared runbook behind the [[RIT-A-0001]] gate → `record-edit-feedback` per decision → `reconcile_session` + `commit_session` → write `<name>-<J>-final.json` (+ ledger) → later `export` enforces the page hard-gate on the render.

## Detailed Design **[REQUIRED]**

**Budget enforcement (REQ-002).** `budget_enforce` reads the [[RIT-I-0019]] `ResumeShapePolicy` budgets (informational pre-job, enforced here) and the tailored resume, emitting a violation per over-budget dimension with the overage amount. No trimming happens in the enforcer; it only quantifies the gap the rankers must close.

**Job-aware ranking (REQ-003, the only substantial new logic).** Three deterministic rankers score each trimmable unit against the **target job** using `resume_kit_matching` + the alias index: skills by (job-match ∧ used-in-experience/summary) > specific-technical > generic/soft/foundational; experience entries by recency ∧ seniority ∧ job-relevance ∧ quantified-outcome, with **compress-before-remove**; bullets by quantified-impact ∧ scope/leadership > tool-only/redundant. The lowest-ranked units become trim candidates until the budget is met; **ties defer** to a decision. Rankers are pure and unit-testable per rule.

**Trims as ChangeProposals through the reused loop (REQ-004/005, NFR-004).** `build_perfect` constructs a `ChangeProposal` per candidate and runs the standard edit-session: `open_session` → `prompt_session` presents ranked candidates → `decide_change` records keep/drop/compress → `reconcile_session`/`commit_session` write behind the hard gate. Application uses the shared change-application runbook ([[RIT-A-0005]]/[[RIT-T-0124]]); feedback uses `record-edit-feedback` folding into `refresh-preferences`. This is the explicit reuse mandate: `perfect` adds ranking, not plumbing.

**Compression not truncation (REQ-007).** Over-length units become claim-gated rewrite `ChangeProposal`s (reuse the `refine`/`align-resume` truth+claim gates). A compression that would drop a claim fails the gate — it is a rewrite, not a cut.

**Stage-appropriate ledger (REQ-006, NFR-002).** Reuse `ContentLedger` with `dropped_by_explicit_decision` (interactive) and `dropped_by_ranked_budget` (auto-fit) added to the allowed reasons — the inverse of the `structure`/`refine` posture where those are forbidden. The ledger gate still refuses *unaccounted* loss. Auto-fit `log()`s every drop.

**Export page-gate (REQ-009).** `resume_kit_export` gains a page-count check against `max_pages`; `perfect` estimates and warns, export hard-gates on the real render with an override flag. This is the one budget that genuinely needs the renderer, so it lives at export.

**Lineage (REQ-011, NFR-003).** A job-specific `final`/`perfect` pointer keyed by job, provenance to the tailored source + job; master lineage untouched (canonical Rule 8). Multiple job-specific finals coexist from one master.

## Testing Strategy **[REQUIRED]**

### Unit Testing
- **Strategy**: Per-ranker table tests (skills/experience/bullets) asserting order for crafted (resume, job) pairs, including tie→defer; `budget_enforce` violation math; compression truth/claim-gate tests (a compression that drops a claim fails); ledger tests (interactive drop = `dropped_by_explicit_decision`; auto-fit drop = `dropped_by_ranked_budget`; unaccounted loss fails); reuse assertions (NFR-004) that `perfect` routes through `open_session`/`decide_change`/`commit_session` and `record-edit-feedback` rather than bespoke paths; export page-gate unit tests with a stub renderer.
- **Coverage Target**: Match existing scoring/facade/export norms; every ranker rule and both ledger reasons have hit + clean cases.
- **Tools**: pytest in `packages/scoring/tests`, `packages/facade/tests`, `packages/export/tests`.

### Integration Testing
- **Strategy (REQ-013)**: E2E `tailored → perfect` over a deliberately over-budget fixture (too many skills/roles/bullets, over-length summary) for a specific job: ranked candidates produced job-weighted; simulated decisions bring it under budget with full ledger accounting; compressions pass truth/claim gates; feedback recorded and preferences refreshed; export page-gate blocks the over-length render and passes after fit; master lineage unchanged.
- **Test Environment**: Local pytest; deterministic ranking (no network/LLM; compression phrasing assist mocked); real renderer for the page-gate path (confined to `packages/export`).
- **Data Management**: Reuse the `resume-a` master + a synthesized bloated tailored fixture for a fixed job.

### System Testing
- **Strategy**: Cross-surface parity — facade/CLI/MCP/API produce identical ranked candidates, identical finals, identical lineage for the same (resume, job, policy). Auto-fit vs interactive parity where decisions match the default ranking.
- **User Acceptance**: Manual dogfood: fit a real bloated tailored resume to two pages, confirming ranked candidates, the reused decision UX, compression-not-truncation, and the export page-gate.
- **Performance Testing**: N/A beyond ensuring rankers are linear and no accidental per-item LLM calls on the deterministic path.

### Test Selection
Prioritize: (1) no silent/unaccounted content loss (ledger gate) and no fabrication (compression truth/claim gates); (2) reuse of the existing suggest/apply/learn stack (NFR-004); (3) job-weighted ranking correctness incl. tie→defer; (4) export page hard-gate on the real render; (5) master non-mutation; (6) cross-surface parity.

### Bug Tracking
Defects tracked as Metis backlog tasks under this initiative; content-loss, fabrication, or master-mutation regressions are release-blocking.

## Cross-Initiative Coordination **[REQUIRED]**

**Sequence:** [[RIT-I-0016]] (baselining, completed) → [[RIT-I-0019]] (`structure`) → [[RIT-I-0020]] (`refine`) → **RIT-I-0021 (this: `perfect`/`fit`)**.

- **Depends on [[RIT-I-0020]]:** consumes the two rules it handed over — the relocated `SUMMARY_TOO_LONG` (length budget) and the `FOUNDATIONAL_SKILL` intent (job-aware relevance trim). Starts after `refine` and the tailoring path are in.
- **Depends on [[RIT-I-0019]]:** reuses the `ResumeShapePolicy` budget fields (informational there, enforced here) and the `ContentLedger` shape (expanded reason set here).
- **Explicit reuse — does NOT rebuild:** the [[RIT-I-0015]] edit-session orchestrator + hard write gate ([[RIT-A-0001]]) for suggest→decide→apply; the [[RIT-A-0005]] / [[RIT-T-0124]] shared change-application runbook for apply mechanics; the [[RIT-I-0013]] feedback + preference stack (`record-edit-feedback`, `refresh-preferences`, `rank-edit-candidates`; `learn-change`/`rank-changes`) for learning from decisions; `resume_kit_matching` + the [[RIT-I-0009]] alias index for job-weighted ranking; the `refine`/`align-resume` truth+claim gates for compressions.
- **Extends [[RIT-I-0007]] export:** adds the page hard-gate to `resume_kit_export`; renderer-confined per the export boundary invariant.
- **Adopts [[RIT-I-0018]]'s severity taxonomy** for budget/trim findings; does not fork it.
- **Respects the canonical model (Rule 8):** job-specific finals are projections; the master (`structure`/`refine`) is never mutated.

## Alternatives Considered **[REQUIRED]**

- **Enforce budgets earlier (in `structure` or `refine`, pre-job).** Rejected — the core reason this pass exists: pre-job trimming can drop the exact skill/role/keyword the target job wants. Budgets must be enforced job-aware, after tailoring.
- **Silent auto-trim to budget.** Rejected: lossy and job-specific removals must be a decision (or an explicit, logged auto-fit). Silent caps read as "covered everything" when they did not. Every drop is accounted for; auto-fit logs what it cut.
- **Build a dedicated fit orchestrator / apply path / feedback store.** Rejected outright per the reuse mandate: the edit-session orchestrator ([[RIT-I-0015]]), shared change-application runbook ([[RIT-A-0005]]/[[RIT-T-0124]]), and feedback/preference stack ([[RIT-I-0013]]) already do exactly this. `perfect` adds only ranking + budget enforcement + the export page-gate.
- **Naive truncation for over-length summary/bullets.** Rejected: truncation loses claims/meaning. Compression = claim-gated rewrite through the existing truth path.
- **Page-gate purely from a JSON heuristic.** Rejected as the *hard* gate: fonts/margins/templates determine real pages. JSON estimate warns during `perfect`; the hard-gate uses the real render at export.
- **Mutate the master to the fitted version.** Rejected: violates canonical Rule 8 (canonical ≠ submitted). Finals are per-job projections; one master yields many finals.
- **Rank blindly / coin-flip ties.** Rejected: ranking is deterministic and ties defer to a decision, preserving "no silent choice of what matters."

## Implementation Plan **[REQUIRED]**

Phased decomposition (tasks created after human approval; each carries a `Recommended Agent: <model> + <effort>`). **Initiative decomposition itself is `opus + high`.**

- **Phase 1 — Budget enforcer + stage ledger.** `budget_enforce` over the [[RIT-I-0019]] `ResumeShapePolicy` budgets → violations; extend `ContentLedger` allowed reasons for this stage (`dropped_by_explicit_decision`, `dropped_by_ranked_budget`, `compressed`) + gate. *(opus + high)*
- **Phase 2 — Job-aware rankers.** Deterministic `rank_skills`/`rank_experience`/`rank_bullets` weighted by the target job (reuse `resume_kit_matching` + alias index); tie→defer; compress-before-remove for jobs. The core new logic. *(opus + high)*
- **Phase 3 — Compression (claim-gated rewrites).** Over-length summary/bullet compression `ChangeProposal`s through the existing truth+claim gates; prohibit truncation. *(opus + medium)*
- **Phase 4 — `build_perfect` over the reused suggest/apply/learn loop.** Wire trims/compressions as `ChangeProposal`s through `open_session`/`prompt_session`/`decide_change`/`reconcile_session`/`commit_session` ([[RIT-I-0015]]/[[RIT-A-0001]]) + shared change-application runbook ([[RIT-A-0005]]/[[RIT-T-0124]]) + feedback ([[RIT-I-0013]]); job-specific `final` pointer + provenance; master non-mutation; **auto-fit** mode. *(opus + high)*
- **Phase 5 — Export page hard-gate.** Page-count check in `resume_kit_export` with override; `perfect` estimate/warn; export hard-gate on the real render. *(opus + medium)*
- **Phase 6 — Surfaces + `perfect`/`fit` skill + workflow wiring.** Facade + CLI/MCP/API parity; the skill reusing the edit-session decision UX; `resume-workflow` final step + export gate. *(opus + medium)*
- **Phase 7 — E2E integration test + docs + version bump.** `tailored → perfect` E2E (over-budget → ranked → decided → under budget, ledger-accounted; compression gates; export page-gate; master unchanged); README/workflow reconcile; version bump. *(opus + medium)*

**Dependencies:** [[RIT-I-0020]] (`refine` + the two relocated rules), [[RIT-I-0019]] (`ResumeShapePolicy` budgets + `ContentLedger`), and the reused stacks [[RIT-I-0015]]/[[RIT-A-0001]], [[RIT-A-0005]]/[[RIT-T-0124]], [[RIT-I-0013]], [[RIT-I-0009]], [[RIT-I-0007]] (export). Final initiative in the pipeline-reshape sequence.