---
id: phase-3-matching-deterministic
level: initiative
title: "Phase 3 — Matching & Deterministic Analysis"
short_code: "RIT-I-0004"
created_at: 2026-08-04T01:30:00+00:00
updated_at: 2026-08-04T01:13:39.297141+00:00
parent: RIT-V-0001
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/active"


exit_criteria_met: false
estimated_complexity: XL
strategy_id: NULL
initiative_id: phase-3-matching-deterministic
---

# Phase 3 — Matching & Deterministic Analysis Initiative

## Context **[REQUIRED]**

Phases 0–2 are complete and pushed. Phase 1 stood up `packages/schemas` + `packages/core`; Phase 2
added `packages/document-parser` (deterministic text extraction + provider-injected structured
parse → canonical `ResumeDocument`). Phase 3 builds the **matching & deterministic analysis** layer:
the engine capabilities that evaluate a resume against a job and across resume variants, with
explainable, mostly no-LLM scoring.

Crucially, the **schema substrate already exists** from Phase 1 (`packages/schemas/.../analysis.py`
and `job.py`): `ATSScore`, `ATSSubScores`, `KeywordGapAnalysis`, `AlignmentReport`,
`RefinementConfig/Stats`, `AnalysisReport`, `JobDescription`, `Requirement`, `RequirementKind`.
Phase 3 implements the algorithms that PRODUCE these models; only genuinely missing result types
(e.g. a variant-comparison result, a best-selection result, a richer explainable match report if the
existing `AnalysisReport` is insufficient) should be added to `schemas`, minimally.

Grounding from `references/reuse-inventory.md` (paths relative to `upstream/apps/backend/app/`),
confirmed against pinned SHA `116f9cc`:
- **Adapt — `services/ats.py:171` `compute_ats_score`** (+ `_compute_skills_coverage:64`,
  `_compute_section_completeness:98`, `_generate_recommendations:129`, `_extract_all_text:33`,
  `_keyword_in_text:51`): fully deterministic, **zero `app.*` imports, zero LLM** (audit's "Likely
  LiteLLM" guess REFUTED). Weighted composite (keyword_match / skills_coverage /
  section_completeness). A strong seed for the `ats` package; Adapt (not Reuse) because the vision
  wants a richer, expanded deterministic ATS check list.
- **Extract/Adapt — `services/refiner.py` deterministic keyword matching**: `calculate_keyword_match:641`,
  `analyze_keyword_gaps:181`, `_keyword_in_text:38`, `_extract_jd_skill_keys:56`. Whole-term matching
  + injectable/non-injectable split; deterministic (`re`), depends only on `app.schemas.refinement`
  (whose models already live in our `schemas`). The matching substrate.
- **Adapt — `services/improver.py:604` `extract_job_keywords(job_description)`** (+ prompt
  `EXTRACT_KEYWORDS_PROMPT` `templates.py:188`): LLM→JSON of required/preferred skills + keywords.
  Must be inverted behind `core.StructuredCompletionProvider`; downstream match/gap is deterministic.
- **Reuse — `tests/evals/scorers.py` structural evaluators** (`jd_keywords_present`, `is_valid_resume`,
  and the fabrication-oriented ones): port `jd_keywords_present`/`is_valid_resume` as reusable
  matching/validation predicates here; the fabrication/truth ones (`no_fabricated_employers`,
  `personal_info_unchanged`, `sections_preserved`) belong to Phase 4 evidence/alignment — do NOT pull
  them forward beyond what matching needs.
- **Adapt — before/after comparison**: `compute_ats_score` + `calculate_keyword_match` run pre/post,
  deterministic; the substrate for `compare-resume-versions`.

Vision Phase 3 explicitly requires implementing the engine behind: `check-resume-ats`,
`check-resume-job-match`, `select-best-resume`, `compare-resume-versions`. NOTE: the CLI/MCP/API
*interfaces* for these are Phase 5 — Phase 3 delivers the reusable core engine functions + result
models, not the command wrappers. Every ported/adapted unit carries a modified-source marker + an
`references/attribution.md` row (SHA `116f9cc`) and characterization tests before behavior change.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Stand up `packages/matching` (`resume_kit_matching`), `packages/ats` (`resume_kit_ats`), and
  `packages/job-parser` (`resume_kit_job_parser`) as `uv`-workspace members depending inward only on
  `resume_kit_schemas` + `resume_kit_core` (never `app.*`, never a concrete LLM provider).
- **Deterministic keyword matching + gap analysis** in `matching`: whole-term match percentage,
  injectable vs non-injectable split, missing-keyword detection — ported from refiner, producing the
  existing `KeywordGapAnalysis` schema; characterization-tested.
- **Deterministic ATS engine** in `ats`: adapt `compute_ats_score` (skills coverage + section
  completeness + weighted composite + recommendations) producing the existing `ATSScore`/`ATSSubScores`,
  and expand toward the vision's broader deterministic ATS check list where feasible without an LLM;
  characterization-tested against upstream on the seed behavior.
- **Explainable job-match scoring** in `matching`: a job-match evaluation producing an explainable
  report (dimensions, weights, evidence/missing-evidence, confidence, recommendations) — building on
  keyword match + requirement coverage; deterministic (LLM optional and out of scope here).
- **Job description parsing** in `job-parser`: adapt `extract_job_keywords` behind
  `core.StructuredCompletionProvider` to produce a canonical `JobDescription` (+ `Requirement`s +
  keywords); deterministic normalization around the provider call; a no-LLM raw-text path that yields
  a `JobDescription` with raw text + any deterministically-extractable fields.
- **select-best-resume** + **compare-resume-versions** engine functions in `matching`: rank multiple
  resumes against a job with explanation; compute deterministic before/after (or A/B) score deltas
  across variants.
- Green toolchain: `ruff`, `mypy --strict`, `pytest` all pass; characterization tests for every
  ported unit; any provider-boundary test uses the in-memory fake from `resume_kit_core.testing`
  (no network). Existing 401 tests stay green.

**Non-Goals:**
- Any alignment/diff/freedom-level/human-in-loop/truth-validation logic (Phase 4) — including the
  fabrication-detection evaluators and `verify_diff_result`.
- CLI/MCP/API/plugin interfaces (Phase 5) and export (Phase 6).
- A concrete LiteLLM provider (later phase); job keyword extraction uses only the `core` Protocol +
  fake in tests.
- LLM-based semantic scoring/reranking — Phase 3 scoring is deterministic and explainable; LLM
  semantic interpretation is a later enhancement.
- Resume improvement / keyword injection (`inject_keywords`, `refine_resume`) — those are alignment
  (Phase 4).

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- **Functional:**
  - REQ-301: `packages/matching`, `packages/ats`, `packages/job-parser` are `uv`-workspace members
    importing cleanly; public APIs exported via `__init__`.
  - REQ-302: `matching` computes deterministic keyword match % + gap analysis into the existing
    `KeywordGapAnalysis` schema, matching upstream refiner behavior (characterization-tested).
  - REQ-303: `ats` produces `ATSScore`/`ATSSubScores` via an adapted `compute_ats_score`, parity-tested
    against upstream on seed inputs; deterministic; no `app.*`, no LLM.
  - REQ-304: `matching` produces an explainable job-match report (dimensions + weights + evidence +
    missing evidence + confidence + recommendations); scoring never rewards keyword repetition alone
    (presence + support + placement per the vision principle).
  - REQ-305: `job-parser` produces a canonical `JobDescription` via an injected
    `StructuredCompletionProvider` (keyword extraction adapted), with a no-LLM raw-text fallback path;
    never imports a concrete provider.
  - REQ-306: `matching` provides `select_best` (rank N resumes vs a job with explanation) and
    `compare_versions` (deterministic score deltas across two/more resume variants).
  - REQ-307: Any new result models (comparison/selection/explainable-match) are added to
    `packages/schemas` minimally and reused, not duplicated per package.
- **Non-Functional:**
  - NFR-301: `mypy --strict` passes for all three packages; `ruff` clean; existing 401 tests stay green.
  - NFR-302: No `app.*` import anywhere in the new packages (enforced by an import-boundary test).
  - NFR-303: No network/LLM in any test — job-parser structured path uses the fake provider.
  - NFR-304: Every ported/adapted unit has a modified-source marker + an `attribution.md` row (SHA
    `116f9cc`).

## Architecture **[CONDITIONAL: Technically Complex Initiative]**

### Overview
Adds the analysis layer above parsing:
```
packages/schemas         — ATSScore, KeywordGapAnalysis, JobDescription, AnalysisReport (+ minimal
                           new comparison/selection/match-report types this phase adds)
packages/core            — provider Protocol, warnings/provenance, InterfaceResponse
packages/document-parser — ResumeDocument production (Phase 2)
packages/matching        — NEW. Deterministic keyword match + gap, explainable job-match scoring,
                           select-best, compare-versions. Depends on schemas + core.
packages/ats             — NEW. Deterministic ATS engine (adapt compute_ats_score, expand checks).
                           Depends on schemas (+ core for warnings). No LLM.
packages/job-parser      — NEW. JobDescription production: keyword extraction behind
                           core.StructuredCompletionProvider + deterministic no-LLM raw-text path.
```
All matching/ATS scoring is deterministic and always available. The only LLM path is job keyword
extraction, invoked through the injected Protocol (fake in tests). `matching` may depend on `ats`
if the job-match report composes ATS sub-scores; keep that dependency direction explicit and acyclic.

## Detailed Design **[REQUIRED]**

Follow the vision extraction order per ported unit: locate upstream (done — see Context) → review →
classify (done — reuse inventory) → **port tests / add characterization tests first** → extract
behind clean boundaries → only then adjust/expand behavior. Concretely:
1. Scaffold the three packages (pyproject/py.typed/tests, workspace + core/schemas deps, toolchain).
2. `matching`: port `calculate_keyword_match`, `analyze_keyword_gaps`, `_keyword_in_text`,
   `_extract_jd_skill_keys` (refiner) into a keyword-matching module producing `KeywordGapAnalysis`;
   characterization-test parity with upstream. Port `jd_keywords_present`/`is_valid_resume` predicates.
3. `ats`: adapt `compute_ats_score` + helpers into an ATS engine producing `ATSScore`; parity-test the
   seed, then add expanded deterministic checks (e.g. contact/section/date presence, formatting risks)
   as additive sub-checks feeding recommendations, without breaking the seed composite.
4. `matching` (job-match): build an explainable `check_job_match(resume, job)` producing a match report
   with per-dimension scores (keyword coverage, required/preferred requirement coverage, evidence
   strength/placement), weights, missing evidence, confidence, recommendations. Reuse ATS sub-scores
   where sensible. Enforce the no-repetition-reward principle.
5. `matching` (select/compare): `select_best(resumes, job)` ranking with explanation;
   `compare_versions(a, b, job)` deterministic score deltas (ATS + match). Add minimal schema result
   types in `schemas` if `AnalysisReport` is insufficient.
6. `job-parser`: adapt `extract_job_keywords` behind `StructuredCompletionProvider` → `JobDescription`
   (+ `Requirement`s), with a deterministic no-LLM raw-text path; provider-boundary tests via the fake.
7. Attribution rows + per-package import-boundary tests.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- **Characterization tests** for keyword match, gap analysis, and `compute_ats_score` — written to
  pass against current upstream behavior BEFORE any modification (prove-it-fails when logic is broken).
- **Unit tests** for expanded ATS checks, explainable job-match scoring (including the
  no-keyword-repetition-reward principle), select-best ranking, and compare-versions deltas.
- **Provider-boundary tests** for job-parser structured extraction using the in-memory fake provider:
  happy path → `JobDescription` with requirements/keywords; malformed output → warnings + fallback;
  no-provider → deterministic raw-text `JobDescription`.
- All deterministic; no network. Existing 401 tests must stay green. Per-package import-boundary tests
  assert no `app.*`/concrete-provider imports.
- Gate: `uv run ruff check packages tests && uv run mypy packages/core packages/schemas packages/document-parser packages/matching packages/ats packages/job-parser && uv run pytest`
  (run `uv sync --all-packages` first — plain `uv sync` skips non-root workspace members).

## Alternatives Considered **[REQUIRED]**

- **One combined `analysis` package instead of matching/ats/job-parser.** Rejected: the vision's
  package architecture separates matching, ats, and job-parser; combining them re-couples distinct
  concerns and complicates the dependency graph (ats must stay LLM-free; job-parser is the only LLM
  path). Three focused packages keep boundaries honest and allow file-disjoint parallel work.
- **New scoring from scratch, ignoring upstream.** Rejected: `compute_ats_score` + refiner keyword
  matching are deterministic, tested, and low-coupled — adapting under characterization protection is
  faster and safer than a rewrite. We expand, not replace.
- **LLM-based semantic match scoring now.** Rejected: the vision wants deterministic, explainable
  scoring first; LLM semantic interpretation is an optional later enhancement and would undermine the
  no-LLM analysis mode.
- **Duplicating result schemas per package.** Rejected: the canonical models already live in
  `schemas`; packages consume them and only minimal new comparison/selection types are added centrally.

## Implementation Plan **[REQUIRED]**

Decomposed by a codex agent into file-disjoint tasks (see child tasks). Expected shape:
1. Scaffold `matching`, `ats`, `job-parser` (may be one scaffold task or one per package) — lands first.
2. `matching` keyword match + gap analysis (refiner port) + char tests.
3. `ats` engine (adapt compute_ats_score) + parity tests, then expanded deterministic checks.
4. `matching` explainable job-match report (may depend on ats).
5. `matching` select-best + compare-versions (+ minimal schema additions if needed).
6. `job-parser` structured keyword extraction behind provider + no-LLM path + fake-provider tests.
7. Attribution + import-boundary tests.
Waves ordered so scaffolding lands first, then file-disjoint modules in parallel; job-match/select/
compare serialize after the keyword+ats primitives they compose.

**Exit criteria:** three packages import cleanly as workspace members; deterministic keyword matching,
gap analysis, and ATS scoring ported + characterization-tested to upstream parity; explainable
job-match report + select-best + compare-versions implemented and unit-tested (no-repetition-reward
enforced); job-parser produces `JobDescription` via injected provider with a no-LLM fallback and
fake-provider tests; every ported unit attributed (SHA `116f9cc`) and marked; no `app.*`/provider
imports (boundary tests); `ruff` + `mypy --strict` + `pytest` all green; existing 401 tests still pass.