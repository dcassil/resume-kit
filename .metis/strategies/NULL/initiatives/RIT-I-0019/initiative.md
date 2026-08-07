---
id: canonical-structure-pass-original
level: initiative
title: "Canonical structure pass: original/base → structure (lossless canonicalization to jsonresume schema)"
short_code: "RIT-I-0019"
created_at: 2026-08-07T18:20:34.331565+00:00
updated_at: 2026-08-07T18:20:34.331565+00:00
parent: RIT-V-0001
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/active"


exit_criteria_met: false
estimated_complexity: L
strategy_id: NULL
initiative_id: canonical-structure-pass-original
---

# Canonical structure pass: original/base → structure (lossless canonicalization to jsonresume schema) Initiative

## Context **[REQUIRED]**

Today the baselining pipeline (shipped in [[RIT-I-0016]]) is `original → base → standard`:

- **`original`** — immutable, faithful ingest behind the `validate-faithfulness` gate.
- **`base`** — `original` after deterministic, auto-safe ATS cleanup (PII strip, date/encoding normalization). Job-independent.
- **`standard`** — `base` after the human-in-the-loop generic best-practices *wording* pass.

Dogfooding the plugin on a real resume (`resume-a.docx` → SoundCloud "Senior Web Engineer" job) surfaced a **structural gap the current pipeline does not fill**: nothing ever forces the resume into a clean, canonical, non-redundant *shape* before wording runs.

Concretely, on a real resume:
- The `check-structure` engine *detects* `NONSTANDARD_SECTION` ("Domains & Industries", "Ventures & Consulting") but marks it `needs_judgment`, so `base`'s auto pass **defers** it — and `build_standard` only consumes *best-practices (wording)* findings, so the deferred structural item is **picked up by nothing**. It is silently dropped. (Verified in `resume_kit_scoring/base_fix.py::apply_auto_fixes` + `resume_kit_facade/baseline.py::build_standard`.)
- There is **no redundancy detection at all**: the fixture carries *both* a "Core Skills" section *and* a full "Technical Skills" section (overlapping skill lists) *and* a "Domains & Industries" section. Nothing flags or merges them.
- There is **no mapping** of arbitrary `customSections` into canonical fields, and **no canonical section-order** normalization. The only `canonical` references in the codebase are in `resume_kit_export/render.py` — render *order*, not structure.

The result: `standard` grooms wording on top of a structurally messy, redundant document, and every downstream job-tailored variant inherits that mess.

This initiative introduces a new **`structure`** pass that sits **between `base` and `standard`** and has exactly one job: **take the resume and losslessly move all of its content into the canonical resume shape defined in [`references/jsonresume.md`](../../references/jsonresume.md)** — canonical sections, canonical field placement, deduped/merged redundant sections, normalized section order — **without adding, dropping, interpreting, trimming, or rewording anything.**

`structure` is deliberately **the first of three planned initiatives**:
1. **This initiative** — add the additive, non-destructive `structure` pass; leave the current `standardize` pass otherwise **as is**, changing only which artifact it reads (it consumes `structure` instead of `base`).
2. *(Follow-on)* — rename/rework `standardize` into a **`refine`** pass (job-independent wording quality; move length/relevance rules out).
3. *(Follow-on)* — add the final **`perfect`/`fit`** pass (job-aware budgets: max skills/pages/jobs, length trims, ranked cuts) after a tailored resume exists.

This initiative is scoped to **(1) only** and is **additive-only**: it must not change `base`, must not change the internals of the `standardize`/`build_standard` wording pass, and must not regress any existing behavior. The single permitted change to the existing pipeline is that `build_standard`'s **input resolution** prefers the new `structure` artifact.

**Canonical model reuse (not rebuild):** `references/jsonresume.md` is the authoritative canonical `Resume` definition for this work (JSON-Resume-derived, stricter: `basics`, `work[]` with `achievements[]` as structured evidence, `skills[]` as `SkillGroup`s, `projects[]`, `education[]`, `certifications[]`, `awards[]`, `publications[]`, `volunteer[]`, `languages[]`, `interests[]`, `references[]`). The canonical model's Architectural Rules (§"Architectural Rules") already state the governing principle this pass enforces: *canonical data is the source of truth; rendered/tailored resumes are projections; separate facts from presentation; never invent evidence; preserve original text.*

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Introduce a new **`structure`** version in the code-owned lineage: `original → base → structure → standard`, with a `structure_resume` / `structure_derived_from` pointer pair in `ProjectConfig`, mirroring the existing `base`/`standard` pointer machinery exactly (additive, backward-compatible).
- Define the **canonical `Resume` schema** from `references/jsonresume.md` as first-class schema types, and produce `resume-structure.json` conforming to it.
- Implement a **read-only, deterministic shape analyzer** that reports, without mutating: custom-section→canonical mappings, unmapped sections, redundant/duplicate-content sections, canonical-field duplicates, embedded-heading-line artifacts, and section-order violations. Budget conditions (skills count, summary length, etc.) may be **reported as informational only** and are **never** acted on here.
- Implement a **strictly non-destructive canonicalizer** that moves content into the canonical shape: map clean custom sections into canonical fields, merge/dedupe redundant sections, strip embedded heading-line artifacts, normalize section order. Every change recorded in a **content ledger**.
- Enforce two hard write gates: a **content-ledger gate** (every substantive input token is `present_after` or accounted for by an allowed non-lossy reason) and a **claims-preserved-across-sections gate** (no employer/title/degree/skill claim added/dropped/altered, evaluated over the *whole* resume rather than a single field).
- Keep the existing `standardize`/`build_standard` pass **behaviorally unchanged**, altering only its **input resolution** so it reads `structure ?? base ?? original`. A thin, additive **projection** bridges the canonical schema to the `BuildDoc`/`ResumeDocument` shape `standardize` already consumes, so `standardize`'s internals are untouched.
- Expose the new capabilities across all surfaces (facade / CLI / MCP / API) and as a plugin skill, and wire the skill into `resume-workflow` between structure and wording — consistent with the established architecture.

**Non-Goals:**
- **Any budget enforcement, trimming, cutting, ranking, or length limiting.** No max skills / max pages / max jobs / summary trim / bullet trim / relevance cut. Those belong to the later **`perfect`/`fit`** pass (initiative 3) which runs *after* a tailored resume exists. This pass keeps the *richest* truthful content, only in canonical shape.
- **Any wording change.** No rewrite, quantification, buzzword removal, verb strengthening, summary tightening. That is the `standardize`→`refine` pass (initiative 2), which this initiative leaves as is.
- **Any evidence interpretation / extraction.** `structure` moves each bullet **verbatim** into `Achievement.text`; it does **not** parse bullets into `action`/`result`/`metrics`, does not synthesize `SkillGroup` semantics beyond preserving the source's own groupings, and never invents evidence. Structured-evidence extraction (metrics, action/result decomposition) is explicitly future work, not this pass.
- **Renaming or reworking `standardize` itself.** The rename to `refine` and the wording-rule reclassification are initiative 2. Here `standardize` changes only its input pointer.
- **Changing `base`, the ingest boundary, or the `-original`/faithfulness contract.**
- **Job-dependent work of any kind** (keywords, terminology, gap analysis) — unchanged, downstream, out of scope.
- **Retiring the ATS engine's `NONSTANDARD_SECTION` finding.** Once the shape analyzer covers section classification, the ATS-owned finding becomes redundant; its removal is a **tracked cleanup task within this initiative's decomposition** (so we do not leave two analyzers reporting the same thing), but it is sequenced last and must not break `base`.

## Requirements **[REQUIRED]**

### User Requirements
- **User Characteristics**: Same population as [[RIT-I-0016]] — a job seeker (non-technical to technical) driving resume-kit through the conversational skill surface, plus automation/agents (e.g. the job-hunter bridge) driving CLI/MCP. Users should never be required to hand-edit JSON. The structure pass is mostly automatic; the only interactive moments are ambiguous section mappings that cannot be resolved deterministically.
- **System Functionality**: After `base` exists, the user (or an agent) can run the structure pass. The system reports the canonical mapping/redundancy/order findings, applies the safe non-destructive canonicalization, and writes `structure`. Ambiguous mappings are surfaced for a decision (or deferred, never guessed). From then on, `standardize` reads `structure`.
- **User Interfaces**: Plugin skill (`update-shape`, conversational) + CLI/MCP/API parity. Auto mode applies only unambiguous safe moves and reports what it deferred; a decision path resolves ambiguous section mappings. No content is ever removed.

### System Requirements
- **Functional Requirements**:
  - REQ-001: **Canonical schema.** Add first-class schema types for the canonical `Resume` per `references/jsonresume.md` (`Resume`, `Basics`, `Location`, `Experience`, `Achievement`, `Metric`, `SkillGroup`, `Project`, `Education`, `Certification`, `Link`, `ResumeDate`, and the remaining optional collections). Validate cardinality rules from the spec (`basics.name` required; `oneOrMore(email,phone)`; `Experience.organization`+`title` required; etc.).
  - REQ-002: **Shape policy (data, not heuristics).** Add a `ResumeShapePolicy` in `packages/policy` (`resume_kit_policy`) defining canonical section order, section alias/mapping rules (keyword→canonical), allowed custom/`other` fallback behavior, and **informational-only budget fields** (no deletion/trim rules in this policy). Project-overridable via `config.json`.
  - REQ-003: **Read-only shape analyzer.** `analyze_resume_shape(resume, policy) -> ShapeReport` in `resume_kit_scoring/shape_analyzer.py`, deterministic and side-effect-free. Findings families: `CUSTOM_SECTION_MAPPED`, `CUSTOM_SECTION_UNMAPPED`, `REDUNDANT_SECTION`, `DUPLICATE_SECTION_CONTENT`, `CANONICAL_FIELD_DUPLICATE`, `EMBEDDED_HEADING_LINE`, `SECTION_ORDER_VIOLATION`. Budget conditions surfaced as **informational** findings only.
  - REQ-004: **Non-destructive canonicalizer.** `apply_shape_transforms(resume, report, decisions=None) -> ShapeFixResult` in `resume_kit_scoring/shape_fix.py`. Auto-safe transforms only: move clean skill/cert/award custom sections into their canonical fields; merge/dedupe redundant sections and canonical-field duplicates via a ledger; strip duplicated heading lines embedded as first list items; normalize section order. Ambiguous/prose-heavy sections (e.g. "Core Skills" prose, "Domains & Industries") become **unresolved mapping candidates** (`needs_user_input`) or preserved verbatim as deliberate `other`/custom content — **never** blindly coerced or dropped.
  - REQ-005: **Content ledger + gate.** Build a `ContentLedger` during transforms with states `present_after | moved | deduped | dropped_as_heading | dropped_as_parser_artifact | dropped_by_explicit_decision | unresolved`. The gate `content_ledger_ok(ledger)` passes only when every substantive input token is `present_after` or accounted for by an allowed reason. **`dropped_by_budget` is not a permitted reason at this stage** (budgets belong to `perfect`). The write is refused if the gate fails.
  - REQ-006: **Claims-preserved-across-sections gate.** Add `claims_preserved_across_sections(before, after)` that extracts each claim type (skills, employers, titles, degrees) from *wherever it lives in the whole resume* — not only `additional.technicalSkills`. This is required because moving a custom "Technical Skills" section into the canonical skills field would, under the existing field-scoped `_claim_set`, falsely read as *added* skills and refuse the write. The existing `claims_preserved` is **left unchanged** (base/standard keep it); the new predicate gates `structure` only.
  - REQ-007: **`build_structure` stage.** Add `build_structure(root, *, answers=None, decisions=None) -> BuildStructureResult` in `resume_kit_facade/baseline.py`, mirroring `build_base`/`build_standard`: resolve `base ?? original`, run analyzer, apply safe transforms + accepted decisions, run the ledger + across-sections claim gates, write `<name>-structure.json` (canonical schema), and `set_version(structure=…, structure_derived_from=source)`.
  - REQ-008: **Config lineage.** Extend `ProjectConfig` with `structure_resume` + `structure_derived_from`; extend `set_version` with `structure=`/`structure_derived_from=` params (same "derived_from without pointer = error" guard); update `resolve_active_resume` to `standard ?? structure ?? base ?? original`. Additive, backward-compatible.
  - REQ-009: **Standardize bridge (additive, standardize unchanged).** Add a deterministic projection `project_builddoc_from_canonical(Resume) -> BuildDoc/ResumeDocument` (the inverse-direction analogue of the [[RIT-A-0002]] `project_scoredoc` pattern). Change `build_standard`'s **source resolution only** to `structure ?? base ?? original`, projecting the canonical structure to the shape it already consumes. `build_standard`'s wording logic is otherwise **untouched**.
  - REQ-010: **Surfaces + skill.** Expose `analyze_resume_shape` and `build_structure` via facade capability functions + CLI (`resume-tool analyze-shape`, `resume-tool build-structure`) + MCP (`resume_analyze_shape`, `resume_build_structure`) + API, with cross-surface parity. Add an `update-shape` plugin skill and wire it into `resume-workflow` after `update-structure`/`base` and before the wording pass.
  - REQ-011: **ATS `NONSTANDARD_SECTION` retirement (sequenced last).** Once the shape analyzer covers section classification, remove/neutralize the redundant `NONSTANDARD_SECTION` emission in `resume_kit_ats/engine.py` so `base` and `structure` do not double-report. Must not change any `base` gate or output shape otherwise.
  - REQ-012: **E2E integration test.** A real-fixture test proving `original → base → structure → standard`: `structure` conforms to the canonical schema, is content-lossless vs `base` (ledger fully accounted), the redundant "Core Skills"/"Technical Skills"/"Domains & Industries" case is merged/mapped, and `standardize` still runs unchanged on the projected structure.
- **Non-Functional Requirements**:
  - NFR-001 (Determinism): The analyzer and the auto-safe transforms are fully deterministic and reproducible for a fixed input. No LLM in the structure pass; ambiguous mappings are deferred to explicit decisions, never model-guessed.
  - NFR-002 (Non-destructiveness / Truth): The pass can never write a `structure` version that loses substantive content (ledger gate) or alters a claim (across-sections claim gate). Both gates are hard, consistent with the RIT-A-0001 write-gate posture. This is the load-bearing invariant.
  - NFR-003 (Additive / Backward compatibility): Projects with only `original`/`base` continue to work; `structure` is optional and additive. `base` and the `standardize` wording logic are behaviorally unchanged. The only pipeline change is `build_standard` input resolution.
  - NFR-004 (Surface parity): facade/CLI/MCP/API produce identical shape reports, identical `structure` output, and identical lineage state for the same input, enforced by parity tests as in prior phases.

## Use Cases **[REQUIRED]**

### Use Case 1: Canonicalize a resume with redundant, non-standard sections (auto)
- **Actor**: Job seeker (or agent) who has a `base` resume.
- **Scenario**: The `resume-a` fixture has `personalInfo`/`workExperience` plus custom sections "Core Skills", "Domains & Industries", and a full "Technical Skills" list that overlaps the flat `additional.technicalSkills`. User runs the structure pass → analyzer reports: "Technical Skills" custom section is a `REDUNDANT_SECTION`/`CANONICAL_FIELD_DUPLICATE` of the canonical skills field; embedded heading lines detected; section order violation. Canonicalizer merges "Technical Skills" into canonical `skills`, dedupes, strips the heading-line artifacts, normalizes order. "Domains & Industries" and prose-heavy "Core Skills" are surfaced as unresolved mapping candidates.
- **Expected Outcome**: `<name>-structure.json` exists in canonical schema, is content-lossless vs `base` (ledger fully accounted), config points `structure` at it, and the ambiguous sections are reported for a decision rather than dropped or coerced.

### Use Case 2: Resolve an ambiguous section mapping (decision)
- **Actor**: Job seeker.
- **Scenario**: The analyzer flags "Ventures & Consulting" as `CUSTOM_SECTION_UNMAPPED`. The skill asks: "Where does 'Ventures & Consulting' belong — Experience, Projects, or keep as a separate section?" User answers "Experience". The canonicalizer moves the roles under it into canonical `work[]` (verbatim `Achievement.text`), records the moves in the ledger, and re-runs the gates.
- **Expected Outcome**: The content lands in the canonical field with zero token loss; the decision is recorded; `structure` is written.

### Use Case 3: Standardize consumes structure with no code change
- **Actor**: Automation running the existing `standardize` pass.
- **Scenario**: `build_standard` resolves its input as `structure ?? base ?? original`, projects the canonical `structure` to the `BuildDoc` shape via the additive projection, and runs its **unchanged** best-practices wording logic.
- **Expected Outcome**: `standard` is produced exactly as before, now seeded from the canonicalized structure; no behavioral change to the wording pass; all existing standard tests still pass.

## Architecture **[REQUIRED]**

### Overview
Follows the established layered architecture: deterministic engines in packages (a new shape analyzer + canonicalizer in `resume-kit-scoring`, canonical schema in `resume-kit-schemas`, policy in `resume-kit-policy`) → a `build_structure` capability in `resume-kit-facade` → thin CLI/MCP/API adapters → an `update-shape` plugin skill. State/versioning lives in the code-owned `ProjectConfig`. Writes pass two hard gates. The canonical `Resume` is the source-of-truth model; the projection to `BuildDoc` is the analogue of the [[RIT-A-0002]] ScoreDoc projection — a pure deterministic read-model transform that keeps `standardize` decoupled from the canonical schema.

### Component Diagram (described)
- **`resume-kit-schemas` (extended)**: canonical `Resume` + sub-models from `references/jsonresume.md`; `ShapeReport`, `ShapeFinding`, `SectionMapping`, `ContentLedger`, `ShapeFixResult`.
- **`resume-kit-policy` (extended)**: `ResumeShapePolicy` (canonical order, alias/mapping rules, informational budgets).
- **`resume-kit-scoring` (extended)**: `shape_analyzer.analyze_resume_shape` (read-only), `shape_fix.apply_shape_transforms` (non-destructive), `claims_preserved_across_sections`, `content_ledger_ok`, and `project_builddoc_from_canonical` (or housed in the projection module alongside `project_scoredoc`).
- **`resume-kit-facade` (extended)**: `build_structure`; `ProjectConfig` `structure_*` pointers; `set_version`/`resolve_active_resume` updates; `build_standard` source-resolution change.
- **`resume-kit-ats` (touched last)**: retire redundant `NONSTANDARD_SECTION`.
- **Surfaces**: facade capabilities + CLI/MCP/API adapters + `update-shape` skill; `resume-workflow` updated.

### Sequence (described)
`base` exists → `analyze_resume_shape(base, policy)` → `apply_shape_transforms(base, report, decisions)` building a `ContentLedger` → `content_ledger_ok` gate + `claims_preserved_across_sections` gate → write `<name>-structure.json` (canonical) → `set_version(structure=…)` → later, `build_standard` resolves `structure ?? base ?? original`, projects canonical→BuildDoc, runs unchanged wording pass → `standard`.

## Detailed Design **[REQUIRED]**

**Canonical schema (REQ-001).** Transcribe `references/jsonresume.md` into pydantic models in `packages/schemas`. Enforce the spec's cardinality/`oneOrMore` rules at validation time. `structure` output validates against this model. Critically, `structure` **moves content verbatim**: each source bullet becomes an `Achievement` with only `text` populated (`action`/`result`/`metrics`/`skills`/`keywords` left empty); source skill groupings become `SkillGroup`s preserving the source's own grouping and keyword lines; the flat `additional.technicalSkills` and any redundant "Technical Skills" custom section are merged/deduped into `skills`. Per the canonical model's Rule 7, retain original text where useful so the move is auditable/reversible.

**Shape policy (REQ-002).** `ResumeShapePolicy` lives in `resume_kit_policy` (with `path_policy.py`/`skill_targets.py`) because it is configuration/data, not analysis. It carries canonical `section_order`, a keyword→canonical alias/mapping table (seed from the ATS engine's existing `_CONVENTIONAL_SECTION_KEYWORDS`, promoted from a flat set to a `dict[str, CanonicalSection]`), allowed `other` fallback behavior, and budget fields **flagged informational-only**. No trim/deletion rules exist in this policy.

**Read-only analyzer (REQ-003).** `analyze_resume_shape` classifies each section against the policy, detects redundancy/duplicate content via token-set overlap (reuse the `resume_kit_matching/keywords.py` tokenizer), detects embedded heading lines (a first list item equal to the section key/heading), and detects order violations. It emits findings with per-family codes and, for mappings, a proposed target + confidence. Budget conditions are surfaced as informational findings and carry no fix affordance here.

**Non-destructive canonicalizer (REQ-004/005/006).** `apply_shape_transforms` performs only lossless moves and records each token's fate in a `ContentLedger`. Clean skill-atom custom sections auto-merge into `skills`; certifications/awards into their canonical fields; heading-line artifacts are stripped as `dropped_as_heading`; parser artifacts (see [[RIT-T-0131]]) as `dropped_as_parser_artifact`; exact duplicates as `deduped`. Ambiguous/prose-heavy sections become `unresolved` (surface as `needs_user_input`) or preserved as deliberate `other`/custom content. Two gates then run: `content_ledger_ok` (no unaccounted substantive token; `dropped_by_budget`/`dropped_by_user_decision` disallowed at this stage) and `claims_preserved_across_sections` (whole-resume claim extraction so re-bucketing is not misread as add/drop). Gate failure refuses the write and surfaces the report — a failure is a bug, not user data.

**Fabrication-safety alignment.** Reuse existing truth substrates where relevant; the structure pass introduces no claims, so `resume_validate_faithfulness`/evidence checks are not re-implemented — the ledger + across-sections claim gate are the stage-appropriate guarantees.

**Standardize bridge (REQ-009, NFR-003).** Add `project_builddoc_from_canonical` next to the [[RIT-A-0002]] projection code. `build_standard` changes exactly one thing — its source resolution — from `base_resume or active_resume` to `structure_resume or base_resume or active_resume`, projecting the canonical structure before its existing analyzer runs. No wording-rule change.

**Config lineage (REQ-008, NFR-003).** Mirror the `base`/`standard` pointer pattern in `project_config.py`: two new optional fields, two new `set_version` params with the existing lineage guard, one added rung in `resolve_active_resume`. Atomic-write preserved; unknown keys preserved.

**ATS retirement (REQ-011).** Last task: neutralize `NONSTANDARD_SECTION` in `resume_kit_ats/engine.py` now that shape analysis owns it, guarded by tests that `base`'s report shape and gates are otherwise unchanged.

## Testing Strategy **[REQUIRED]**

### Unit Testing
- **Strategy**: Table-driven tests per shape rule (positive + clean cases) asserting finding families and proposed mappings; canonical-schema validation tests (cardinality/`oneOrMore`); ledger-gate adversarial tests (a transform that drops a token fails `content_ledger_ok`; a merge that loses a skill fails); `claims_preserved_across_sections` regression (moving a "Technical Skills" custom section into canonical `skills` does **not** read as added claims); config lineage/backward-compat (`standard ?? structure ?? base ?? original`; only-`original` still works).
- **Coverage Target**: Match existing package norms; every new rule has ≥1 hit and ≥1 clean case; both gates have ≥1 pass and ≥1 refuse case.
- **Tools**: Existing pytest suites in `packages/scoring/tests`, `packages/schemas/tests`, `packages/facade/tests`.

### Integration Testing
- **Strategy (REQ-012)**: End-to-end over the `resume-a` fixture: ingest → `base` → `build_structure` produces canonical, content-lossless `structure` (full ledger accounting) with the redundant Core/Technical Skills + Domains & Industries case merged/mapped → `build_standard` runs **unchanged** on the projected structure and still writes `standard`. Assert artifacts, lineage pointers, and that no existing `standard` test regresses.
- **Test Environment**: Local pytest, no network/LLM (structure pass is fully deterministic).
- **Data Management**: Commit the `resume-a` (or an equivalent multi-custom-section) fixture under the scoring/facade test trees.

### System Testing
- **Strategy**: Cross-surface parity — facade/CLI/MCP/API emit identical shape reports, identical `structure` output, identical lineage state for the same input.
- **User Acceptance**: Manual dogfood of the `update-shape` skill on `resume-a`, confirming auto moves + the ambiguous-mapping decision UX and that nothing is removed.
- **Performance Testing**: N/A — deterministic, cheap; assert no accidental LLM calls in the structure path.

### Test Selection
Prioritize the load-bearing invariants: (1) non-destructiveness (ledger gate) and claim-safety (across-sections gate); (2) `standardize`-unchanged behavioral parity on the projected structure; (3) canonical-schema conformance; (4) config lineage/backward-compat; (5) cross-surface parity.

### Bug Tracking
Defects tracked as Metis backlog tasks under this initiative; non-destructiveness or claim-safety regressions are release-blocking. Note existing related backlog: [[RIT-T-0131]] (faithfulness phantom ADDED_TOKENS + unscanned customSection keys) — the `dropped_as_parser_artifact` ledger reason defends against its symptom, and fixing RIT-T-0131 upstream removes the need; [[RIT-T-0132]] (which best-practices rules can fire auto_suggestible) informs the follow-on `refine` initiative, not this one.

## Cross-Initiative Coordination **[REQUIRED]**

**Sequence:** [[RIT-I-0016]] (baselining `original→base→standard`, completed) → **RIT-I-0019 (this: insert `structure`)** → *follow-on 2* (`standardize`→`refine`) → *follow-on 3* (`perfect`/`fit`).

- **Builds on [[RIT-I-0016]] — consume, do not modify:** the `base` artifact, the `ProjectConfig` version-lineage substrate ([[RIT-T-0113]]), and the `build_base`/`build_standard` facade shape. This initiative is **additive**: `base` and the `build_standard` wording logic are unchanged; only `build_standard`'s input resolution changes.
- **Reuses the [[RIT-A-0002]] / [[RIT-I-0017]] projection pattern:** `project_builddoc_from_canonical` is the inverse-direction analogue of `project_scoredoc(BuildDoc)→ScoreDoc`. Housed alongside it. Scoring/ATS continue to read ScoreDoc; when they run on `structure`-seeded documents, the canonical→BuildDoc projection precedes the existing BuildDoc→ScoreDoc projection. No change to the ScoreDoc contract.
- **Hands off to follow-on 2 (`standardize`→`refine`):** this initiative deliberately does **not** touch wording rules. The reclassification of `SUMMARY_TOO_LONG` (length→`perfect`) and `FOUNDATIONAL_SKILL` (relevance→`tailor`) and the rename to `refine` are that initiative's scope. We only guarantee `standardize` reads `structure`.
- **Hands off to follow-on 3 (`perfect`/`fit`):** **all** budget/trim/rank/length concerns (max skills/pages/jobs, summary/bullet trims, ranked cuts) are explicitly deferred there, to run *after* a tailored resume exists so cuts are job-aware. This pass only *reports* budget conditions informationally.
- **Touches [[RIT-I-0018]]'s territory minimally:** RIT-I-0018 (industry guidance audit) owns the consolidated dos/donts inventory and severity taxonomy; the shape findings here **adopt** that taxonomy and do not fork it.

## Alternatives Considered **[REQUIRED]**

- **Fold `structure` into `standard` (no new stage/pointer).** Considered and explicitly weighed. Pros: one fewer pointer, smaller surface. Rejected for this initiative because it would change the behavior of the working `standardize` pass (overloading it with structural concerns and forcing a schema bridge inside it), violating the additive-only constraint. A separate stage keeps the diff to existing working code minimal (one input-resolution line) and cleanly separates the non-destructive structural transform from the wording transform, each with its own gate posture and its own resumable artifact. The fold remains a viable future consolidation if the extra pointer proves not worth it.
- **Emit `structure` in the existing `ResumeDocument`/`BuildDoc` schema (canonically organized), not the richer `jsonresume.md` schema.** Rejected: the user-designated canonical definition is `references/jsonresume.md`, and its structured-evidence model (`Achievement`, `SkillGroup`, `Metric`, `Link`) is where downstream tailoring/export want to land. Emitting the canonical schema now — with an additive projection back to `BuildDoc` for the unchanged `standardize` — pays the schema cost once and matches the codebase's existing "canonical model + deterministic projection" pattern ([[RIT-A-0002]]).
- **Change `standardize` to read the canonical schema directly (no projection).** Rejected for this initiative: it would modify the `standardize` internals, violating additive-only. The projection is the minimal bridge. Migrating `standardize`/`refine` to consume canonical natively is a candidate for follow-on 2.
- **Enforce budgets / trim here (max skills, length caps).** Rejected on principle: pre-job trimming can delete content a target job needs. This pass keeps the richest truthful content; budgets are informational-only and enforced job-aware in `perfect`/`fit`.
- **Extract structured evidence (metrics/action/result) while moving into `Achievement`.** Rejected: that is interpretation, risks fabrication, and likely needs an LLM — out of scope for a deterministic, lossless *move*. `Achievement.text` is populated verbatim; evidence extraction is future work.
- **Strict token-equality gate instead of a content ledger.** Rejected: token equality is too brittle — legitimate dedupe/heading-strip/normalization change the token set. The ledger accounts for each token's fate against an allowlist of non-lossy reasons, enforcing "strict but never silently destructive."
- **Remove `NONSTANDARD_SECTION` from the ATS engine first.** Rejected as an ordering: retiring it before the shape analyzer covers section classification would leave a detection gap. It is sequenced **last** in the decomposition.

## Implementation Plan **[REQUIRED]**

Phased decomposition (tasks to be created after human approval of this breakdown; each task will carry a `Recommended Agent: <model> + <effort>` per the decomposition rubric). **Initiative decomposition itself is `opus + high`.**

- **Phase 1 — Canonical schema + shape schemas.** Transcribe `references/jsonresume.md` into `packages/schemas` models with cardinality/`oneOrMore` validation; add `ShapeReport`/`SectionMapping`/`ContentLedger`/`ShapeFixResult`. Foundational; every later phase consumes these. *(opus + high)*
- **Phase 2 — Shape policy.** `ResumeShapePolicy` in `resume_kit_policy` (canonical order, keyword→canonical alias table seeded from `_CONVENTIONAL_SECTION_KEYWORDS`, informational-only budgets, `other` fallback). *(opus + medium)*
- **Phase 3 — Read-only shape analyzer.** `analyze_resume_shape` with all finding families, deterministic; reuse the matching tokenizer for redundancy/duplicate detection. No writes. *(opus + high)*
- **Phase 4 — Non-destructive canonicalizer + gates.** `apply_shape_transforms` + `ContentLedger`; `content_ledger_ok`; `claims_preserved_across_sections`. The load-bearing correctness phase. *(opus + high)*
- **Phase 5 — `build_structure` + config lineage + projection bridge.** `build_structure` in facade; `ProjectConfig` `structure_*` pointers; `set_version`/`resolve_active_resume` updates; `project_builddoc_from_canonical`; change `build_standard` source resolution only. *(opus + high)*
- **Phase 6 — Surfaces + `update-shape` skill + workflow wiring.** Facade capabilities + CLI/MCP/API adapters + parity; `update-shape` skill; `resume-workflow` insertion between structure and wording. *(opus + medium)*
- **Phase 7 — E2E integration test + docs + version bump.** Real-fixture `original→base→structure→standard` test (lossless ledger, redundancy merge, standardize-unchanged parity); README/docs reconcile; version bump. *(opus + medium)*
- **Phase 8 — Retire ATS `NONSTANDARD_SECTION` (sequenced last).** Neutralize the redundant ATS finding now that shape analysis owns it; guard `base` report shape/gates unchanged. *(sonnet + medium)*

**Dependencies:** builds on [[RIT-I-0016]] (base + version-lineage substrate, completed) and the [[RIT-A-0002]] projection pattern (completed). No blocking dependency on active initiatives. Follow-on initiatives 2 (`standardize`→`refine`) and 3 (`perfect`/`fit`) depend on this one landing.