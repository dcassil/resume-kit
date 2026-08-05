---
id: resume-baselining-original-to-base
level: initiative
title: "Resume baselining: original to base to standard onboarding pipeline"
short_code: "RIT-I-0016"
created_at: 2026-08-05T16:41:16.870587+00:00
updated_at: 2026-08-05T18:26:55.510826+00:00
parent: RIT-V-0001
blocked_by: [RIT-I-0015, RIT-I-0017]
archived: false

tags:
  - "#initiative"
  - "#phase/active"


exit_criteria_met: false
estimated_complexity: M
strategy_id: NULL
initiative_id: resume-baselining-original-to-base
---

# Resume baselining: original → base → standard onboarding pipeline

## Context **[REQUIRED]**

Today the toolkit is a **job-tailoring** pipeline. When resume-kit is initialized in a project (or a user supplies a new resume), the deterministic ingest boundary (RIT-I-0014) produces a single immutable artifact — `<name>-original.json` — behind a `validate-faithfulness` hard gate. From there every downstream skill (`check-keyword-match`, `inject-keywords`, `align-terminology`, …) operates **against a specific job description**. There is no step that gets the resume itself into good shape *before* any job enters the picture.

This creates two problems:

1. **We tailor from a weak baseline.** If the original resume has structural/ATS problems (missing sections, unparseable formatting, detached dates) or weak wording (duty-listing instead of accomplishments, buzzwords, no quantification), every job-tailored variant inherits those defects. We optimize keyword overlap on top of a resume a recruiter or parser may already reject.
2. **There is nowhere to encode "the candidate's best generic resume."** `config.json` only tracks `active_resume` / `active_job` and the pipeline only knows `-original`. There is no job-independent, cleaned-and-strengthened version to serve as the stable input for all future tailoring.

This initiative introduces a **baselining / onboarding flow** that runs once per resume, before any tailoring, and establishes a three-version lineage:

- **`original`** — the immutable, faithful ingest of what the user gave us (already exists; unchanged).
- **`base`** — `original` after fixing basic **ATS structural / format / parse** problems. The goal of `base` is simply: *an ATS-passing, cleanly-parseable resume.* No wording judgment yet.
- **`standard`** — `base` after a human-in-the-loop **generic best-practices** pass (structure + wording quality, NOT against any job). `standard` becomes the default input for **all** downstream tailoring.

The best-practices model driving `base` and `standard` is derived from a consolidated list of dos/donts compiled from major ATS vendors (Workable, SmartRecruiters, Jobvite, Lever, Indeed, LinkedIn). Only the **job-independent** subset of that list is in scope here; the job-dependent items already live in (or belong to) the tailoring skills and are explicitly out of scope (see Non-Goals and the companion notes in `.metis/adrs/`).

This work reuses two existing substrates:
- The deterministic **ATS structure engine** (`packages/ats` → `resume_check_ats_structure` / `check-ats-structure`), which is already job-independent and emits `section_completeness` + `recommendations`. `base` extends this engine; it does not replace it.
- The **enforced human-in-the-loop edit loop** (RIT-I-0015): the `standard` walkthrough is an edit session subject to the same write gate, truth validation, and feedback logging.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Introduce a **version lineage** `original → base → standard` in the code-owned project state (`ProjectConfig` / `config.json`), with `standard` becoming the resolved default input for all downstream tailoring capabilities.
- On init / new-resume, run an **ATS structural + format + parse check** (job-independent) and drive fixes — **auto or interactive, user's choice** — producing `base`. `base` should reliably pass a basic ATS structural check.
- Build a **generic best-practices scoring engine** (job-independent): structure quality + wording quality (action verbs, first-person/duty openers, quantification presence, buzzwords, bullet length, summary quality, skills hygiene, length/relevance, consistency). This is distinct from the job-match composite score.
- Provide a **human-in-the-loop walkthrough** that takes the user item-by-item through everything the best-practices engine flags: auto-suggesting fixes where possible, and **eliciting user-supplied information** where the fix requires facts we don't yet have (e.g. turning a duty into an evidence-backed, quantified accomplishment). On acceptance, save `standard`.
- Enforce **truth/faithfulness** across the whole flow: no fabricated metrics or claims are introduced; `base` stays faithful to `original`, and `standard` edits pass the existing truth gate.
- Expose the new capabilities across all surfaces (facade / CLI / MCP / API) and as plugin skills, consistent with the existing architecture, and wire them into the `resume-workflow` guide as the mandatory pre-tailoring phase.

**Non-Goals:**
- **Any job-specific work.** Keyword matching, JD-driven tailoring/terminology, gap analysis, seniority-vs-target framing — all remain in the tailoring skills (`check-keyword-match`, `inject-keywords`, `align-terminology`, `identify-resume-gaps`). The `standard` score is explicitly *not* computed against a job.
- **Export / file-format / submission concerns** (DOCX vs PDF, selectable-text verification, parsed-field round-trip, upload checks). These belong to `export-resume` / `resume_export`. The one adjacent item we *do* touch is the descriptive, name-bearing filename when writing `base`.
- **Rebuilding truth/faithfulness validation.** We *reuse* `resume_validate_truth` / `validate-faithfulness`; we do not re-implement them.
- **True source-file layout/rendering ATS detection** (real multi-column, tables, text-boxes, headers/footers, images/scanned PDFs, shapes behind text). The current structure engine operates on parsed JSON + a text scan and structurally *cannot* see these. Deep source-file (PDF/DOCX) inspection is called out as a **dependency/risk** and is scoped as a bounded extension at the ingest boundary — see Requirements REQ-011 and Risks. If it proves large, it splits into a follow-on initiative.
- Changing the ingest boundary's faithfulness contract or the `-original` artifact.

## Requirements **[REQUIRED]**

### User Requirements
- **User Characteristics**: The end user is a job seeker (non-technical to technical) driving resume-kit through a conversational skill surface. They can supply real accomplishment facts (numbers, scope, outcomes) when prompted but should never be *required* to hand-edit JSON. A power user may prefer fully-automatic fixes; another may want to approve each change.
- **System Functionality**: After init or providing a new resume, the system runs an ATS structural check, offers to fix issues automatically or interactively, and saves `base`. It then scores `base` on generic best practices and walks the user through each flagged item, suggesting or eliciting fixes, and saves `standard` on acceptance. From then on, tailoring uses `standard`.
- **User Interfaces**: Plugin skills (conversational), plus CLI/MCP/API parity for programmatic use. Interactive mode presents one item at a time with a concrete suggested change or a targeted question; auto mode applies only the deterministic, truth-safe suggestions and reports what was deferred as needing user input.

### System Requirements
- **Functional Requirements**:
  - REQ-001: `ProjectConfig` gains version pointers for `base` and `standard` (in addition to `original`), plus enough provenance to know each was derived from its predecessor. Atomic write semantics preserved.
  - REQ-002: `set-active` / active-resume resolution treats `standard` as the default tailoring input when present, falling back to `base`, then `original`.
  - REQ-003: A job-independent **ATS structural check** (extend `resume_check_ats_structure`) detects and reports: missing/!conventional sections and section order, missing employer/title/location/date-range separation, missing or inconsistent date formats, contact-info completeness (name/phone/professional-email/city+state/readable links) and prohibited PII (SSN, DOB, marital status, references-on-request), placeholder/template/leftover-AI-prompt text, and formatting/parse risks currently covered by `_FORMATTING_RISK_PATTERNS` (extended for the visual-element donts detectable from parsed text).
  - REQ-004: A **fix driver** for `base` supporting two modes — `auto` (apply only deterministic, truth-preserving fixes: section renames to conventional names, date-format normalization, PII stripping, placeholder removal, ordering) and `interactive` (present each fix for accept/reject/edit). Output written as `<name>-base.json` behind the faithfulness gate (`base` must remain faithful to `original`).
  - REQ-005: A new **generic best-practices scoring engine** (job-independent), deterministic-first with optional LLM assist, producing a structured report of flagged items across: experience-bullet quality (weak/duty openers, first-person, action verb, action→result, bullet length, one-accomplishment-per-bullet, buried result, duplicate bullets, equal-detail-per-job), quantification presence & vagueness ("significantly", "many", vanity/activity metrics), summary quality, buzzword/generic-language wordlist, skills-section hygiene (bars/ratings, foundational tools, over-long inventory, dupes), length & relevance, and cross-document consistency (tense, punctuation, capitalization, first/third person, date-format).
  - REQ-006: Each flagged item is classified as **auto-suggestible** (we can propose a concrete rewrite truthfully) or **needs-user-input** (fix requires facts we don't have — e.g. a metric, team size, outcome). The latter drives a targeted elicitation prompt.
  - REQ-007: A **human-in-the-loop walkthrough** capability that iterates flagged items, integrates with the RIT-I-0015 edit-session orchestrator + hard write gate, records accept/reject via the feedback log, and on completion writes `<name>-standard.json`.
  - REQ-008: All new capabilities exposed via facade + CLI + MCP + API with cross-surface parity, plus plugin skills, and wired into `resume-workflow` as the mandatory pre-tailoring phase.
  - REQ-009: **Truth guardrail** — every applied change (in `base` fixes and `standard` walkthrough) passes the existing truth/faithfulness validation; no capability may introduce an unsupported claim or fabricated number. User-supplied facts are accepted but still routed through evidence/truth checks where applicable.
  - REQ-010: An **end-to-end integration test** over a real fixture resume proving `original → base → standard` produces the three artifacts, `base` passes the structural check, and `standard` is selected as the tailoring default.
  - REQ-011 **[bounded / at-risk]**: Source-file (PDF/DOCX) structural signals for the parse-risk donts that JSON cannot express (multi-column, tables, text-boxes, headers/footers, image-only/scanned). Scoped as a bounded ingest-time detector emitting warnings into the `base` structural report; if analysis shows it is large, it is deferred to a follow-on initiative rather than expanded here.
- **Non-Functional Requirements**:
  - NFR-001 (Determinism): Structural checks and the auto-suggestible portion of best-practices scoring are deterministic and reproducible for a fixed input; any LLM assist is confined to soft judgments and is clearly separated (mirrors the existing engine's "deterministic seed score, enriched recommendations" contract).
  - NFR-002 (Safety/Truth): The flow can never write a version that fails faithfulness (`base`) or truth (`standard`) validation; the write gate is hard, consistent with RIT-A-0001.
  - NFR-003 (Backward compatibility): Projects that only have `-original` continue to work; `base`/`standard` pointers are optional and additive. No breaking change to existing config consumers.
  - NFR-004 (Surface parity): CLI/MCP/API/facade behavior is identical for the same inputs, enforced by parity tests as in prior phases.

## Use Cases **[REQUIRED]**

### Use Case 1: Init a project with a resume that has ATS problems
- **Actor**: Job seeker onboarding a new resume.
- **Scenario**: User runs init / provides a resume → deterministic ingest produces `original` → system runs the ATS structural check and reports issues (e.g. "Skills" section titled "My Superpowers", dates in inconsistent formats, a street address + DOB present) → user chooses **auto-fix** → system applies deterministic, truth-preserving fixes and writes `base` → reports what it changed and anything it deferred as needing judgment.
- **Expected Outcome**: `<name>-base.json` exists, passes the structural check, remains faithful to `original`; config points `base` at it.

### Use Case 2: Strengthen a duty-listing resume into accomplishments (interactive)
- **Actor**: Job seeker who wants a strong generic resume.
- **Scenario**: After `base`, system scores generic best practices and walks the user through flagged items. For a bullet "Responsible for maintaining the billing service," the item is classified **needs-user-input**: the system explains the weakness and asks a targeted question ("What changed because of your work — e.g. reliability, cost, or time saved, and by roughly how much?"). User answers "cut billing incidents ~40% over two quarters." System proposes a truthful rewrite ("Reduced billing-service incidents ~40% across two quarters by …"), user accepts. Buzzword items (e.g. "results-driven team player" in the summary) are **auto-suggestible** and proposed directly.
- **Expected Outcome**: On acceptance of the walkthrough, `<name>-standard.json` is written; all edits passed truth validation; accept/reject feedback logged; config points `standard` at it and it becomes the tailoring default.

### Use Case 3: Programmatic baselining via MCP/CLI
- **Actor**: An automation / another agent (e.g. job-hunter bridge).
- **Scenario**: Calls the MCP/CLI baselining capabilities to run the structural check, apply `auto` fixes, and retrieve the best-practices report (with items classified auto vs needs-input) without a human present. needs-input items are returned for later human resolution rather than auto-fabricated.
- **Expected Outcome**: `base` produced deterministically; `standard` only finalized once needs-input items are resolved by a human; no fabricated facts introduced.

## Architecture **[REQUIRED]**

### Overview
Follows the established layered architecture: deterministic engines in packages (`resume-kit-ats` and a new/extended best-practices analyzer) → capability functions in `resume-kit-facade` → thin adapters in CLI/MCP/API → plugin skills orchestrating the conversation. State/versioning lives in the code-owned `ProjectConfig`. The `standard` walkthrough runs on top of the RIT-I-0015 edit-session orchestrator and hard write gate (RIT-A-0001), and all writes pass the existing faithfulness/truth validators.

### Component Diagram (described)
- **`resume-kit-ats` (extended)**: `resume_check_ats_structure` gains the fuller job-independent structural ruleset (sections/order, entry separation, date consistency, contact completeness + PII, placeholder/AI-leftover scan, extended formatting-risk patterns). Emits an `AtsStructureReport` enriched with per-issue codes + fix affordances.
- **`resume-kit-best-practices` (new analyzer, or a new module within ats)**: job-independent wording/structure quality scoring → structured `BestPracticesReport` of flagged items, each tagged `auto_suggestible | needs_user_input` with a suggested change or an elicitation prompt.
- **Version/state**: `ProjectConfig` gains `base` / `standard` pointers + provenance; active-resume resolution prefers `standard`.
- **Fix drivers**: a `base` fixer (auto/interactive) and a `standard` walkthrough, both writing behind the hard gate and logging feedback.
- **Surfaces**: facade capabilities + CLI/MCP/API adapters + plugin skills; `resume-workflow` updated to require baselining before any tailoring.

### Sequence (described)
init/new-resume → ingest(`original`) → `check-ats-structure` → fix driver (auto|interactive) → faithfulness gate → write `base` → best-practices score(`base`) → walkthrough(items: auto-suggest | elicit) → per-edit truth gate + write gate + feedback log → on accept-all → write `standard` → set `standard` as default → (later) tailoring uses `standard`.

## Detailed Design **[REQUIRED]**

**Version lineage & config (REQ-001/002/ NFR-003).** Extend `ProjectConfig` (`packages/facade/src/resume_kit_facade/project_config.py`) with optional `base`/`standard` document pointers (and their source provenance), mirroring the existing `active_resume` / `active_resume_source` shape. Active-resume resolution becomes `standard ?? base ?? original`. All writes keep the existing atomic-write guarantee. Additive and backward-compatible.

**ATS structural engine extension (REQ-003/004, NFR-001).** Build on `packages/ats` `engine.py`. Keep the existing deterministic seed contract; add issue **codes** and machine-readable fix affordances so the fix driver can act. Structural rules are all job-independent and derived from the in-scope dos/donts: conventional section names + order, employer/title/location/date-range separation, date-format presence *and consistency*, contact completeness + prohibited PII, placeholder/leftover-AI-prompt scan, and extended `_FORMATTING_RISK_PATTERNS`. The `auto` fixer applies only deterministic, truth-preserving transforms (renames, normalization, PII stripping, ordering); anything requiring judgment is deferred to the walkthrough, never auto-fabricated.

**Best-practices scoring engine (REQ-005/006, NFR-001).** New job-independent analyzer. Deterministic-first: weak/duty-opener detection ("Responsible for", "Duties included", "Worked on/Helped with"), first-person openers (I/my/me), action-verb presence, action→result heuristics, bullet length, one-accomplishment-per-bullet, buried-result, duplicate-bullet detection, equal-detail-per-job, quantification presence + vagueness wordlist ("significantly", "many/various/numerous/large", activity/vanity metrics), buzzword wordlist (hardworking, results-driven, team player, rock star/ninja/guru, strategic/innovative/visionary-without-evidence, corporate filler, unsupported superlatives), summary length/shape, skills hygiene (bars/ratings, foundational tools, over-long inventory, dupes, all-tech-only-in-skills), length/relevance, and whole-document consistency (tense, punctuation, capitalization, first/third person, date format). Optional LLM assist is confined to the soft judgments (e.g. "is this a real accomplishment?") and clearly separated. Each flagged item carries `auto_suggestible` (concrete truthful rewrite) or `needs_user_input` (targeted elicitation prompt).

**Walkthrough → `standard` (REQ-007/009, NFR-002).** Runs as an edit session on the RIT-I-0015 orchestrator + hard write gate. Iterates flagged items: auto-suggestible items proposed directly; needs-input items pose a targeted question, take the user's fact, and generate a truthful rewrite that must pass the truth validator before it can be applied. Accept/reject logged via the feedback log (feeding preference learning). On acceptance of the full set, write `<name>-standard.json` and point config at it.

**Surfaces & workflow (REQ-008).** Facade capabilities + CLI/MCP/API adapters with parity tests; plugin skills for the structural check+fix, the best-practices score, and the walkthrough. Update `resume-workflow` so tailoring is gated behind the existence of `standard` (or an explicit user override).

## Testing Strategy **[REQUIRED]**

### Unit Testing
- **Strategy**: Table-driven tests per structural rule and per best-practices rule against crafted resume fragments (positive + negative cases), asserting issue codes, `auto_suggestible` vs `needs_user_input` classification, and that `auto` fixes are truth-preserving. Config lineage/resolution unit tests (`standard ?? base ?? original`, backward-compat when only `original` exists).
- **Coverage Target**: Match existing package norms; every new rule has at least one hit and one clean case.
- **Tools**: Existing pytest suites in `packages/ats/tests` and facade tests.

### Integration Testing
- **Strategy (REQ-010)**: End-to-end over a real fixture resume (reuse an existing fixture, e.g. the Staff-FS resume used in prior integration tests): ingest → `base` (auto) passes structural check and faithfulness → best-practices report produced with correct item classification → simulated walkthrough acceptance → `standard` written and selected as default. Assert the three artifacts exist and config points correctly.
- **Test Environment**: Local pytest, no network/LLM required for the deterministic path (LLM-assisted soft judgments mocked/stubbed).
- **Data Management**: Committed fixtures under the ats/facade test trees.

### System Testing
- **Strategy**: Cross-surface parity tests (facade/CLI/MCP/API produce identical structural + best-practices output and identical lineage state for the same input), consistent with prior phases.
- **User Acceptance**: Manual dogfood on a real resume through the plugin skills, confirming interactive vs auto modes and the needs-input elicitation UX.
- **Performance Testing**: Not a concern at this scale; deterministic passes are cheap. N/A beyond ensuring no accidental per-item LLM calls in the deterministic path.

### Test Selection
Prioritize: (1) truth-safety of `auto` fixes, (2) correct auto-vs-needs-input classification, (3) config lineage/backward-compat, (4) cross-surface parity. These are the load-bearing invariants.

### Bug Tracking
Defects tracked as Metis backlog tasks under this initiative; truth-safety or faithfulness regressions are release-blocking.

## Cross-Initiative Coordination **[REQUIRED]**

This initiative interlocks with two siblings; the boundaries below prevent duplicated or conflicting work. **Sequence:** [[RIT-A-0002]] (decided) → [[RIT-I-0017]] → **RIT-I-0016** → [[RIT-I-0018]]; both RIT-I-0016 and RIT-I-0017 sit after [[RIT-I-0015]] (the edit-session orchestrator).

- **Depends on [[RIT-I-0017]] / [[RIT-A-0002]] (ScoreDoc/BuildDoc projection) — consume, do not rebuild:**
  - **ScoreDoc is the scoring/segmentation read model.** 0017 introduces a pure deterministic `project_scoredoc(BuildDoc) → ScoreDoc` and repoints all scoring — including `packages/ats` `check_ats_structure`, `skills_coverage`, `section_completeness` — to read ScoreDoc's canonical sections/entities/zoned index, never raw BuildDoc fields. **Our REQ-003/REQ-005 engines (the structural-check extension and the new best-practices analyzer) read ScoreDoc**, not `additional.technicalSkills` or hand-rolled section segmentation.
  - **Ordering on the shared `check_ats_structure`.** Both initiatives touch this engine: 0017 changes *where* it reads (ScoreDoc); we change *what* it checks (the fuller job-independent ruleset + issue codes/fix affordances). To avoid writing new rules against BuildDoc and reworking them, **0017's projection + ats repoint (RIT-T-0106/RIT-T-0108) land before our Phase 2 engine extension**, and our new rules are authored against ScoreDoc from the start.
  - **Reuse the "what the ATS sees" report.** 0017 owns the single read-only ATS-view report (facade/CLI/MCP/API + skill). Our `base` structural-check step **surfaces that report** rather than printing a second ATS-view.
  - **Feed the projection.** Where our `base` fixer renames/normalizes/reorders sections, those canonicalization decisions **feed 0017's `customSections → KeywordZone` mapping** (RIT-T-0106) so projection and normalization agree. Per [[RIT-A-0002]], if we force a canonical structure, 0017's projection simplifies but its contract does not change.
  - **No ProjectConfig conflict.** 0017 is additive scoring only; the `base`/`standard` version pointers (REQ-001/002) are **owned here** and are additive/backward-compatible.

- **Owned here; referenced by [[RIT-I-0018]] (industry guidance audit):**
  - **The grooming-finding severity taxonomy.** This initiative establishes the single severity model (hard-gate / warning / recommendation / review-note / out-of-scope-future) used by best-practices findings. 0018 **adopts and may extend** it; it must not define a competing taxonomy.
  - **The job-INDEPENDENT best-practices engine** and the **job-INDEPENDENT slice** of the consolidated ATS dos/donts. 0018 owns the **job-DEPENDENT** remainder (tailoring, employer-terminology mirroring, keyword-in-context/anti-stuffing, required>optional, review/version-selection, export/submission hygiene) and is the single consolidated inventory of the full list — we **reference its job-independent slice** rather than forking the master list.
  - **REQ-011 (bounded source-file PDF/DOCX layout parse-risk detection).** This is the render-catching gap that [[RIT-A-0002]] and 0018 both defer to us. We own it; 0018 references REQ-011 rather than re-scoping layout / selectable-text checks.

- **Shared guardrails (reused, not rebuilt):** the truth/faithfulness gates (`resume_validate_truth`, `candidate_evidence_build`, `resume_validate_faithfulness`) and the [[RIT-I-0015]] edit-session orchestrator + hard write gate ([[RIT-A-0001]]).

## Alternatives Considered **[REQUIRED]**

- **Fold baselining into the existing tailoring flow instead of a distinct phase.** Rejected: it conflates job-independent quality with job-specific optimization, keeps us tailoring from a weak baseline, and gives no stable `standard` artifact. The whole point is a clean pre-tailoring baseline.
- **Only two versions (`original` → `standard`), skipping `base`.** Rejected: it merges "make it parse/pass ATS structurally" with "make the wording strong," which have different fix policies (deterministic/auto-safe vs judgment/needs-user-input) and different validation gates (faithfulness vs truth). Keeping `base` as an explicit ATS-passing checkpoint makes each stage's contract clean and lets `auto` mode stop at a safe point.
- **Reuse the composite ATS score's `recommendations` as the best-practices model.** Rejected: those recommendations are job-keyword-driven; a generic wording model (weak verbs, buzzwords, quantification, bullet quality) genuinely does not exist today and must be built job-independently.
- **Auto-generate accomplishments/metrics with the LLM to avoid asking the user.** Rejected outright: violates the truth/faithfulness contract. needs-input items must elicit real facts; fabrication is never acceptable.
- **Do full source-file (PDF/DOCX) layout ATS detection now.** Deferred: the current engine works on parsed JSON and cannot see columns/tables/text-boxes; true detection is a sizable new capability. Scoped as bounded warnings (REQ-011) with a follow-on initiative if large, to avoid ballooning this one.

## Implementation Plan **[REQUIRED]**

Phased decomposition (tasks to be created after human approval of this breakdown; each task will carry a `Recommended Agent: <model> + <effort>` per the decomposition rubric):

- **Phase 1 — Version lineage substrate.** Extend `ProjectConfig` with `base`/`standard` pointers + provenance; update active-resume resolution (`standard ?? base ?? original`) and `set-active`; backward-compat + unit tests. *(foundational — opus + high)*
- **Phase 2 — ATS structural engine extension + `base` fixer.** Add the job-independent structural ruleset with issue codes + fix affordances; implement the auto/interactive fix driver writing `base` behind the faithfulness gate. *(opus + high)*
- **Phase 3 — Generic best-practices scoring engine.** New job-independent analyzer with the full deterministic ruleset + auto-suggestible/needs-user-input classification; optional isolated LLM assist. *(opus + high)*
- **Phase 4 — `standard` walkthrough capability.** Edit-session walkthrough on the RIT-I-0015 orchestrator + hard write gate, elicitation for needs-input items, truth-gated rewrites, feedback logging, writes `standard`. *(opus + medium)*
- **Phase 5 — Surfaces + skills + workflow wiring.** Facade capabilities, CLI/MCP/API adapters + parity, plugin skills, and `resume-workflow` gating tailoring behind `standard`. *(opus + medium)*
- **Phase 6 — E2E integration test + docs + version bump.** Real-fixture `original → base → standard` test, README/docs reconcile, version bump. *(opus + medium)*
- **Phase 7 (conditional) — Bounded source-file parse-risk detector (REQ-011).** Ingest-time warnings for column/table/text-box/header-footer/scanned signals; split to a follow-on initiative if analysis shows it is large. *(opus + medium)*

**Dependencies:** builds on RIT-I-0014 (ingest boundary / `-original` + faithfulness gate) and RIT-I-0015 (edit-session orchestrator + hard write gate + feedback log), which is currently active — Phase 4 should follow RIT-I-0015's orchestrator landing.