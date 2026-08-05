---
id: scoredoc-buildoc-projection
level: initiative
title: "Separate scoring representation (ScoreDoc) from build representation (BuildDoc) via deterministic projection"
short_code: "RIT-I-0017"
created_at: 2026-08-05T17:00:00.000000+00:00
updated_at: 2026-08-05T17:00:00.000000+00:00
parent: RIT-V-0001
blocked_by: [RIT-I-0015]
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: M
strategy_id: NULL
initiative_id: RIT-I-0017
---

# Separate scoring representation (ScoreDoc) from build representation (BuildDoc) via deterministic projection Initiative

## Context **[REQUIRED]**

A single structured resume model — `ResumeDocument` (`packages/schemas/src/resume_kit_schemas/resume.py`)
— currently serves three distinct jobs: **build** (source of truth for the finished resume + export),
**score** (ATS structure + keyword/job-match analysis), and **learn** (feedback/preference derivation).
These pull in different directions and the conflation now produces measurable defects.

- **Scoring reads build-shaped fields directly.** `matching/keywords.py:197-213` and `ats/engine.py:215`
  read `additional.technicalSkills` and walk the raw resume dict. When a resume legitimately carries
  skills inside a *categorized* section rather than that one hardcoded field, the keywords are
  under-counted — the observed **85.8 -> 75.8** score drop, where tokens an ATS would have read fine were
  sitting in a section the scorer never looked at.
- **The score does not reflect what a machine reads.** A real ATS never sees our JSON; it reads the
  rendered artifact, extracts text, and re-segments it into canonical sections and entities (name,
  contact, per-role title/company/dates -> computed years-of-experience). Scoring build-shaped fields
  measures *intent*, not *ATS reality*.
- **Build and score cannot evolve independently.** Because scoring couples to build field names, changing
  the build schema (custom sections, an eventual "ideal structure") risks silently breaking scoring.

The decision on how to resolve this is captured in **[[RIT-A-0002]]** (decided): split into **BuildDoc**
(today's `ResumeDocument`, unchanged) and a derived **ScoreDoc** (canonical ATS view), produced by a
**pure deterministic projection** `BuildDoc -> ScoreDoc` rather than by rendering and re-extracting text.
This keeps scoring deterministic and offline, adds no bundled extractor, and is **purely additive** — the
build schema, renderer, and export are untouched.

### Relationship to other work
- **Depends on [[RIT-I-0015]]** landing first (the edit loop). No code dependency on its internals, but
  this initiative is sequenced after it to avoid churning the same scoring/analysis surfaces mid-flight.
- **Deliberately disjoint from the companion "resume baselining / ideal structure" initiative
  ([[RIT-I-0016]]).** All BuildDoc-shape questions — custom sections vs. forced canonical structure,
  renderer fidelity — live there. This initiative only stops scoring from reading build-shaped fields.
  The one thing projection cannot do (catch a *render* bug) is RIT-I-0016's concern, or a later optional
  parity check (per [[RIT-A-0002]]). If RIT-I-0016 forces resumes into a canonical structure, this
  initiative's projection simplifies but does not change contract.
- **Downstream consumers of ScoreDoc — this initiative is the substrate.** Both [[RIT-I-0016]] (resume
  baselining) and [[RIT-I-0018]] (industry guidance audit) **read ScoreDoc and reuse the "what the ATS
  sees" report** rather than re-deriving scoring or building a second report. Concretely:
  - **Shared `check_ats_structure` ordering.** RIT-I-0016 *extends* `packages/ats` `check_ats_structure`
    with a fuller job-independent ruleset while this initiative *repoints* it onto ScoreDoc. To avoid
    rework, **this initiative's projection + ats repoint ([[RIT-T-0106]], [[RIT-T-0108]]) land before**
    RIT-I-0016's engine extension, and RIT-I-0016 authors its new rules against ScoreDoc.
  - **Section canonicalization feeds the projection.** If RIT-I-0016's `base` fixer renames/normalizes
    sections, those decisions inform this initiative's `customSections → KeywordZone` mapping
    ([[RIT-T-0106]]); contract is unchanged, mapping only simplifies.
  - **Report is the single ATS-view surface.** RIT-I-0018 specifies the "an ATS score does not guarantee
    recruiter advancement" messaging, which **lands on this initiative's score + report surfaces**; its
    scoring-path guidance inherits this initiative's determinism/offline/no-LLM invariant.
- **Sequence:** [[RIT-A-0002]] (decided) → **RIT-I-0017** → [[RIT-I-0016]] → [[RIT-I-0018]]. No
  ProjectConfig interaction: this initiative is additive scoring only; the `base`/`standard` version
  pointers are owned by RIT-I-0016.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Introduce a **ScoreDoc** representation: canonical ATS sections + extracted entities (name, contact,
  per-role title/company/date-range -> computed YoE) + a **zoned keyword index** (token -> zone).
- Implement a **pure deterministic projection** `BuildDoc -> ScoreDoc` in code — no rendering, no text
  extraction, no new dependency, identical output for identical input.
- **Repoint every scoring path to read only ScoreDoc**, never BuildDoc field names. Keyword/match scoring
  harvests from all zones with weights (**experience > skills-list > summary**) plus recency.
- Structurally fix the **85.8 -> 75.8** class of bug: categorized skills score correctly because the
  projection harvests every zone.
- Surface a read-only **"what the ATS sees"** report (detected sections + entities + computed YoE + zoned
  keyword breakdown) across facade + CLI + MCP + API + a plugin skill, per the existing parity norm.

**Non-Goals:**
- **Not** modifying `ResumeDocument`/BuildDoc, the renderer, or export in any way. Purely additive.
- **Not** scoring the rendered artifact, bundling a PDF/DOCX text extractor, or adding a parse-confidence
  or source-map model (explicitly rejected for the base in [[RIT-A-0002]]).
- **Not** introducing new score *types* — `check-ats-structure` (structural) and `check-job-match`
  (content) keep their identity; ScoreDoc is the shared substrate they read from.
- **Not** any LLM/provider dependency or network call in a scoring command — projection and scoring stay
  deterministic and offline.
- **Not** resolving BuildDoc-shape / custom-sections / render-fidelity questions — those belong to the
  companion baselining initiative [[RIT-I-0016]].

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- **Functional Requirements**
  - REQ-001: A `ScoreDoc` schema exists in `packages/schemas` with: canonical ATS **sections** (at least
    Experience, Education, Skills, Summary, Projects, Other), extracted **entities** (name, email, phone,
    links; per experience: title, company, date range -> parsed start/end -> computed duration; total
    computed YoE; degrees/institutions), and a **zoned keyword index** mapping each surfaced token to the
    zone(s) it appears in (experience / skills_list / summary / education / other).
  - REQ-002: A pure function `project_scoredoc(BuildDoc) -> ScoreDoc` deterministically produces ScoreDoc
    from a `ResumeDocument`, including mapping `customSections` (keyed by `SectionType`) into canonical
    zones by section type. Identical input yields byte-identical ScoreDoc.
  - REQ-003: Match/keyword scoring (`packages/matching`) reads **only** ScoreDoc's zoned index — never
    `additional.technicalSkills` or other BuildDoc field names — and applies zone weights
    (experience > skills_list > summary) plus recency weighting.
  - REQ-004: ATS scoring (`packages/ats`) — `skills_coverage`, `section_completeness`, and
    `check-ats-structure` — reads its inputs from ScoreDoc sections/entities/zoned index, not from raw
    BuildDoc fields.
  - REQ-005: The **85.8 -> 75.8** regression fixture scores correctly (categorized skills counted) under
    the new path; a golden test pins the corrected score.
  - REQ-006: A read-only **"what the ATS sees"** report capability is exposed across facade + CLI + MCP +
    API returning detected sections, extracted entities + computed YoE, and the zoned keyword breakdown.
  - REQ-007: A plugin skill surfaces the ATS-view report and is wired into `resume-workflow` at the
    appropriate (analysis) step.
- **Non-Functional Requirements**
  - NFR-001: Every new capability follows the cross-surface parity norm (facade capability + CLI + MCP +
    API where applicable) with parity tests, consistent with prior phases.
  - NFR-002: Projection and all scoring are deterministic and offline — no clock reads inside models
    (caller-supplied timestamps where dates are computed), no network, no LLM in any scoring command.
  - NFR-003: Purely additive and backward-compatible: BuildDoc/`ResumeDocument`, renderer, export, and
    existing result schemas keep working; existing score consumers see the corrected (not restructured)
    numbers, and any shape additions are optional/defaulted.

## Architecture **[CONDITIONAL: Technically Complex Initiative]**

### Overview
Scoring is re-seated on a derived representation instead of the build model:

```
BuildDoc (ResumeDocument)                          source of truth — UNCHANGED
  -> project_scoredoc(BuildDoc) -> ScoreDoc        pure deterministic projection (code)
        ScoreDoc = { sections[], entities{}, zoned_keyword_index{} }
  -> matching  (job-match / keyword coverage)  reads ScoreDoc zoned index + weights   deterministic
  -> ats       (skills_coverage / structure)   reads ScoreDoc sections + entities     deterministic
  -> report    ("what the ATS sees")           renders ScoreDoc read-only             deterministic
```

The renderer, export, and BuildDoc are outside this box entirely. The projection is the single new
load-bearing component; scoring becomes a pure consumer of its output.

### Component impact
- **Schemas** (`packages/schemas`): new `scoredoc.py` — `ScoreDoc`, `ScoreSection`, `ScoreEntities`,
  `ZonedKeywordIndex` (+ a `KeywordZone` enum). No change to `resume.py`.
- **Projection** (location TBD in design task — likely a new `packages/scoring` or within `ats`):
  `project_scoredoc()` incl. date parsing -> YoE and `customSections`->zone mapping.
- **Matching** (`packages/matching/keywords.py`): replace `_extract_all_text` / hardcoded
  `additional.*` reads with ScoreDoc zoned-index consumption + zone/recency weights.
- **ATS** (`packages/ats/engine.py`): repoint `_compute_skills_coverage`, `_compute_section_completeness`,
  `check_ats_structure` onto ScoreDoc.
- **Facade + CLI + MCP + API**: new `ats-view` (or similarly named) report capability + parity tests.
- **Skills**: a new "what the ATS sees" report skill; `resume-workflow` wiring.

### Sequence (projection + rescore)
1. Caller supplies a BuildDoc (existing structured resume) and, where dates matter, a reference "now".
2. `project_scoredoc` produces ScoreDoc: segments sections, extracts entities, computes YoE, builds the
   zoned keyword index.
3. Matching and ATS scoring read ScoreDoc only; the report renders ScoreDoc read-only.

## Detailed Design **[REQUIRED]**

See the decomposed tasks for per-surface design. Design invariants:
- **ScoreDoc is derived, never authored.** Nothing writes ScoreDoc by hand; it is always the output of
  `project_scoredoc`. Scoring code must not reach back into BuildDoc.
- **Zero BuildDoc field names in scoring.** The success test for the repoint is a grep-clean scoring
  layer: no `technicalSkills`/`additional`/`workExperience` literal reads in matching/ats scoring paths.
- **Determinism is a hard contract.** Date->YoE computation takes a caller-supplied reference time; no
  clock reads in the projection. Golden fixtures pin BuildDoc->ScoreDoc.
- **The projection's home is a design decision** (first task): a new `packages/scoring` package vs.
  extending `ats`. Chosen for lowest coupling and clean import boundaries; captured before implementation.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

### Unit Testing
- **Strategy**: Golden-fixture projection tests — known BuildDoc (incl. a categorized-skills custom
  section) -> asserted ScoreDoc (sections, entities, computed YoE, zoned index). Determinism test: same
  input -> identical ScoreDoc. Entity/YoE edge cases (open-ended "Present" ranges, missing dates).
  Zone-weighting unit tests (a token proven in experience outweighs the same token in a bare skills
  list). Scoring-reads-ScoreDoc guard (no BuildDoc field-name reads).
- **Tools**: existing pytest setup.

### Integration Testing
- **Strategy**: End-to-end over a real resume/job fixture proving (a) the **85.8->75.8** case now scores
  correctly with categorized skills counted, (b) `check-ats-structure` and `check-job-match` produce
  coherent numbers off the shared ScoreDoc, (c) the "what the ATS sees" report returns identical content
  across CLI/MCP/API/facade (parity), (d) build/export are byte-for-byte unaffected.
- **Data Management**: reuse existing resume/job fixtures; add a categorized-skills fixture that
  reproduces the regression.

### Test Selection
Prioritize (1) the projection golden fixtures + determinism (highest blast radius), (2) the 85.8->75.8
regression fix, then the scoring repoint parity, then the report cross-surface parity.

## Alternatives Considered **[REQUIRED]**

- **Score the rendered artifact (render -> extract -> re-segment).** Rejected for the base in
  [[RIT-A-0002]]: truest to ATS reality and catches render bugs, but bundles a PDF/DOCX extractor,
  introduces vendor-variance nondeterminism, and needs parse-confidence + a source map — all fighting the
  deterministic/offline character. The render-catching gap is deferred to [[RIT-I-0016]] or an optional
  later parity check.
- **Keep the single model and just teach the scorer to read more fields.** Rejected: perpetuates the
  coupling, so every future build-shape change re-breaks scoring, and yields no ATS-view artifact for the
  report.
- **Put ScoreDoc + projection inside `ats` rather than a new package.** Considered; deferred to the design
  task. Leaning to a dedicated boundary so both `ats` and `matching` depend on projection without a cycle.
- **Fold the report into an existing check rather than a new capability.** Rejected: the "what the ATS
  sees" view is a distinct read-only artifact and deserves its own capability for clarity and parity.

## Implementation Plan **[REQUIRED]**

Sequenced after [[RIT-I-0015]] lands. Decision recorded in [[RIT-A-0002]]. Decomposition:

1. **RIT-T-0104** — Design task: choose the projection's home package + finalize the ScoreDoc schema
   shape (sections/entities/zoned index) and the projection contract (date->YoE reference-time input,
   customSections->zone mapping). *(opus + high)* — load-bearing; every downstream task consumes it.
2. **RIT-T-0105** — `ScoreDoc` schema in `packages/schemas` (`ScoreDoc`, `ScoreSection`, `ScoreEntities`,
   `ZonedKeywordIndex`, `KeywordZone`), backward-compatible additive. *(opus + high)*
3. **RIT-T-0106** — `project_scoredoc(BuildDoc) -> ScoreDoc`: segmentation, entity + date->YoE extraction,
   customSections->zone mapping, zoned keyword index. Golden-fixture + determinism tests. *(opus + high)*
4. **RIT-T-0107** — Repoint **matching** (`keywords.py`) onto the ScoreDoc zoned index with zone +
   recency weighting; remove hardcoded `additional.*` reads. *(opus + medium)*
5. **RIT-T-0108** — Repoint **ats** (`engine.py`: skills_coverage, section_completeness,
   check-ats-structure) onto ScoreDoc sections/entities. *(opus + medium)*
6. **RIT-T-0109** — "What the ATS sees" report capability across facade + CLI + MCP + API with parity
   tests. *(opus + medium)*
7. **RIT-T-0110** — Plugin skill for the ATS-view report + `resume-workflow` wiring. *(sonnet + medium)*
8. **RIT-T-0111** — End-to-end integration test (incl. the 85.8->75.8 regression fixture) + README
   reconcile + version bump. *(opus + medium)*

Dependency spine: 0104 (design) -> 0105 (schema) -> 0106 (projection) -> 0107 & 0108 (repoint
matching/ats, parallel) -> 0109 (report) -> 0110 (skill) -> 0111 (closes).
