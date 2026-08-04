# Apache-2.0 Attribution Ledger

> Engineering compliance record for selective reuse of Resume-Matcher code, tests, prompts,
> and schemas. This file is a Phase 0 deliverable. Update it before porting any subsystem.
> Not legal advice.

---

## Upstream Repository Identity

| Field | Value |
|-------|-------|
| Repository URL | https://github.com/srbhr/Resume-Matcher |
| Pinned full commit SHA | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` |
| License | Apache-2.0 |
| Local clone path | `./upstream/` (gitignored reference clone, not distributed product code) |
| NOTICE file | None present at pinned SHA |
| Audit date | 2026-08-03 |

Phase 0 wrote **no product code**. `./upstream/` is a gitignored reference clone used only for
read-only audit evidence; nothing under it is distributed as part of resume-kit. This ledger, the
reuse inventory, and the upstream audit are the only Phase 0 deliverables. The rows below record
provenance obligations that apply *when* later phases actually port material — no porting has
occurred yet.

The upstream LICENSE file is a standard Apache-2.0 text. No NOTICE file is present at the
pinned SHA, so there are no embedded third-party attribution notices to propagate from that
file. If a NOTICE file appears in a future upstream commit, re-audit before updating the pin.

---

## Concrete Engineering Compliance Obligations

These obligations apply whenever resume-kit ports, extracts, or adapts any material from
Resume-Matcher. They are derived directly from the Apache-2.0 license text.

### 1. Retain copyright and attribution notices

Every source file copied from upstream must preserve the original copyright header, if one is
present. Do not strip, reword, or relocate upstream copyright notices when porting code.
If an upstream file has no copyright header, note that in the modification note column of the
provenance table below.

### 2. Include the Apache-2.0 license text

The Apache-2.0 license text must be present in this repository when resume-kit distributes
any covered work (source or binary). The license is already present at `./LICENSE`. Verify
that file is not removed or replaced during repackaging.

### 3. Mark modified files prominently

Any upstream file that is modified — even lightly — must carry a prominent notice that
the file has been changed. Place this notice at the top of the file in a comment block:

```python
# Derived from Resume-Matcher (Apache-2.0)
# Upstream: apps/backend/app/<path>
# Pinned SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc
# Modified: <brief description of changes>
```

Files ported without any modification still need an origin comment, but do not need a
"Modified" line. Files that are substantially rewritten beyond recognition should be
marked as "Adapted from" rather than "Derived from" and should still record the upstream
path and SHA.

### 4. Track upstream path and SHA per ported subsystem

The provenance table below is the canonical record. Every ported file, schema, prompt, or
test must have a row. Update the table before committing any ported material. Future agents
extracting subsystems must add their rows before their extraction PR is merged.

### 5. Avoid using Resume-Matcher trademarks as product identity

Do not use "Resume Matcher", "Resume-Matcher", or the upstream project's branding, logos, or
product names as the identity of resume-kit or any package it ships. Attribution in comments,
this ledger, and documentation is required and permitted. Product naming and promotion must
use resume-kit's own identity.

### 6. No additional restrictions on downstream use

Apache-2.0 does not permit imposing additional restrictions on recipients. If resume-kit adds
its own license, that license must not restrict rights already granted by Apache-2.0 for the
upstream-derived portions.

---

## Provenance Table

> This table is **reconciled** against `references/reuse-inventory.md` (RIT-T-0003). Every subsystem
> classified **Reuse**, **Extract**, or **Adapt** in that inventory has a corresponding row below,
> using the inventory's subsystem naming, upstream paths (line-anchored where the inventory anchors
> them), and target packages. Replace/New subsystems are **not** attributed here — Replace items are
> listed in the "Intentionally Excluded" section to confirm they were reviewed, and New items have no
> upstream material to attribute. The Pinned SHA for every row is
> `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` (stated once here rather than repeated per row, matching
> the inventory's single-SHA policy).

Upstream paths are relative to `apps/backend/`. Attribution requirement for every code/prompt/test row
is the same Apache-2.0 obligation set: **retain any copyright header; mark modified files prominently;
include LICENSE** — abbreviated below as "standard obligations".

### Reuse rows (port largely unchanged)

| Subsystem (inventory name) | Upstream path(s) | Material | Modification note | Target pkg |
|---|---|---|---|---|
| MarkItDown PDF/DOCX→Markdown extraction | `app/services/parser.py:119` (`parse_document`) | code | Standard obligations. Pure markitdown/pdfminer text extraction ported largely unchanged | document-parser |
| Date restoration (month re-hydration) | `app/services/parser.py:35,40` (`restore_dates_from_markdown`, `_extract_markdown_dates`) | code | Standard obligations. Pure-regex helpers extracted standalone; logic preserved | document-parser |
| Structural resume evaluators (eval scorers) | `app/tests/evals/scorers.py:100,117,138,152,161` (`sections_preserved`, `no_fabricated_employers`, `personal_info_unchanged`, `jd_keywords_present`, `is_valid_resume`) | tests/code | Standard obligations. Ported as reusable validation predicates as well as tests | evidence (+ tests) |
| Prompt-injection sanitizer | `app/services/improver.py:48` (`_sanitize_user_input`, `_INJECTION_PATTERNS:29`) | code | Standard obligations. Deterministic security guard reused as-is | policy |
| AI-phrase blacklist / replacements | `app/prompts/refinement.py:4,71` (`AI_PHRASE_BLACKLIST`, `AI_PHRASE_REPLACEMENTS`); `app/services/refiner.py:233` (`remove_ai_phrases`) | prompts/code | Standard obligations. Dictionary-based scrub reused | alignment/policy |

### Extract rows (move out of `app.*` with minimal behavioral change)

| Subsystem (inventory name) | Upstream path(s) | Material | Modification note | Target pkg |
|---|---|---|---|---|
| Diff application engine (allowed paths + gates) | `app/services/improver.py:226` (`apply_diffs`), `:80` (`_ALLOWED_PATH_PATTERNS`), `:118` (`_is_path_allowed`), `:123` (`_is_path_blocked`) | code | Standard obligations. Extracted from service; path-policy split to `policy`, application to `alignment` | alignment (+ policy) |
| Blocked fields | `app/services/improver.py:94,101` (`_BLOCKED_PATH_PREFIXES`, `_BLOCKED_FIELD_NAMES`) | code | Standard obligations. Policy constants separated from service; generalized into freedom-aware policy table | policy |
| Original-value verification | `app/services/improver.py:215` (`_verify_original_matches`) | code | Standard obligations. Extracted as pure function; no behavioral change | alignment |
| Skill-addition gates | `app/services/improver.py:376,709,754` (`_build_allowed_skill_target_keys`, `verify_skill_target_plan`); `app/services/refiner.py:290` (`validate_master_alignment`) | code | Standard obligations. Deterministic gate logic extracted; freedom-level integration is new | policy + alignment |
| Malformed / unsupported change rejection | `app/services/improver.py:289–408` (reject branches in `apply_diffs`) | code | Standard obligations. Reject/report logic extracted; reporting interface adapted | alignment |
| Omitted-content preservation | `app/services/improver.py:335–363` (reorder salvage), `:59` (`_check_for_truncation`, `_preserve_personal_info`) | code | Standard obligations. Preservation logic extracted; no behavioral change | alignment |
| Structural / diff verifier (truthfulness checks) | `app/services/improver.py:430` (`verify_diff_result`) | code | Standard obligations. Deterministic structural verifier extracted | alignment + evidence |
| Structured diff computation | `app/services/improver.py:1224` (`calculate_resume_diff`) | code | Standard obligations. Deterministic field-level diff extracted | alignment |
| Deterministic keyword match / gap analysis | `app/services/refiner.py:181,641,38,56` (`analyze_keyword_gaps`, `calculate_keyword_match`, `_keyword_in_text`, `_extract_jd_skill_keys`) | code | Standard obligations. Deterministic matching substrate extracted | matching |
| Pydantic domain schemas | `app/schemas/models.py:140–923` (`ResumeData`, `PersonalInfo`, `Experience`, `Education`, `Project`, `AdditionalInfo`, `CustomSection`, `ResumeChange`, `ResumeFieldDiff`, `ResumeDiffSummary`, `ImproveDiffResult`) | schemas | Standard obligations. Re-namespaced; **domain models split from HTTP DTOs** in same file; tracker/web DTOs excluded | schemas |
| Refinement schemas | `app/schemas/refinement.py` (`KeywordGapAnalysis`, `AlignmentViolation`, `AlignmentReport`, `RefinementConfig`, `RefinementStats`, `RefinementResult`) | schemas | Standard obligations. Ported; re-namespaced | schemas + matching |
| Fabrication detection & removal | `app/services/refiner.py:290,591` (`validate_master_alignment`, `fix_alignment_violations`) | code | Standard obligations. Deterministic truth guard extracted; seeds truth engine | evidence/alignment |
| Prompt string constants | `app/prompts/templates.py`, `app/prompts/refinement.py`, `app/prompts/enrichment.py`, `app/prompts/resume_wizard.py` | prompts | Standard obligations. Pure constant strings extracted; original strings attributed here (adaptation of individual prompts tracked in Adapt rows) | llm |
| JSON extraction / retry helpers | `app/llm.py:218–352` (`_extract_message_text`, `_to_code_block`, JSON-fence parsing within `complete`/`complete_json`) | code | Standard obligations. Pure text/JSON-repair helpers isolated from LiteLLM transport | llm |

### Adapt rows (valuable implementation, needs new API/boundaries/behavior)

| Subsystem (inventory name) | Upstream path(s) | Material | Modification note | Target pkg |
|---|---|---|---|---|
| LiteLLM provider integration | `app/llm.py:11,559` (`Router`, `_normalize_api_base:115`, `_scrub_secrets:373`, `resolve_api_key:411`) | code | Standard obligations. Adapt behind a `StructuredCompletionProvider` Protocol; config-singleton coupling dropped for explicit DI | llm |
| LLM config | `app/llm.py:440,492` (`get_llm_config`, `get_model_name`, `get_safe_max_tokens`, `LLMConfig`); `app/config.py` | code | Standard obligations. File-singleton replaced with injected config object; web/DB settings dropped | llm |
| Resume-to-JSON parsing | `app/services/parser.py:144` (`parse_resume_to_json`) | code/prompts | Standard obligations. LLM provider injected as protocol; direct `app.llm` import removed; date-restore + validate kept as deterministic wrapper | document-parser |
| Job-keyword extraction | `app/services/improver.py:604` (`extract_job_keywords`); prompt `EXTRACT_KEYWORDS_PROMPT` (`app/prompts/templates.py:188`) | code/prompts | Standard obligations. Standalone function with explicit LLM provider; no persistence dependency | job-parser + matching |
| Improvement / tailoring prompts | `app/prompts/templates.py:242–363` (`IMPROVE_RESUME_PROMPT_{NUDGE,KEYWORDS,FULL}`, `DIFF_IMPROVE_PROMPT`, `KEYWORD_INJECTION_PROMPT`); `app/prompts/refinement.py:138` | prompts | Standard obligations. Adapted for freedom-level parameters and truth constraints | llm |
| Truthfulness prompts | `app/prompts/templates.py:211,230` (`CRITICAL_TRUTHFULNESS_RULES_TEMPLATE`/`CRITICAL_TRUTHFULNESS_RULES`; no-fabrication clauses) | prompts | Standard obligations. Adapted for claim-provenance and truth-validation policy | policy + llm |
| Skill-target planning | `app/services/improver.py:839,754` (`generate_skill_target_plan` LLM + `verify_skill_target_plan` deterministic); `app/prompts/templates.py:492` (`SKILL_TARGET_PLAN_PROMPT`) | code/prompts | Standard obligations. Planner (LLM) separated from verifier (deterministic gate, also in Extract rows) | alignment |
| Diff generation | `app/services/improver.py:506,910,1474` (`generate_resume_diffs`, `improve_resume`, `generate_improvements`) | code | Standard obligations. Generation adapted behind provider interface; output enriched with provenance fields | alignment |
| Diff verification | `app/services/improver.py:430` (`verify_diff_result`, `verify_diffs` path) | code | Standard obligations. Deterministic verifier (same source as the Extract "structural verifier" row); adapted to return structured provenance records | alignment |
| Match scoring | `app/services/refiner.py:641` (`calculate_keyword_match`); `app/routers/resumes.py:462` (`_build_ats_score`, web-coupled → rebuilt) | code | Standard obligations. Deterministic keyword match preserved; router-side assembly rebuilt in `matching` with explainability + weighting | matching + ats |
| ATS scoring engine | `app/services/ats.py:171` (`compute_ats_score`, `_compute_skills_coverage:64`, `_compute_section_completeness:98`, `_generate_recommendations:129`) | code | Standard obligations. Deterministic, zero `app.*` imports (spot-checked). Adapted/extended into the richer resume-kit ATS engine; existing 2-factor score is the seed | ats |
| Cover-letter generation | `app/services/cover_letter.py:36,90,139` (`generate_cover_letter`, `generate_outreach_message`, `generate_resume_title`); prompts `COVER_LETTER_PROMPT`, `OUTREACH_MESSAGE_PROMPT`, `GENERATE_TITLE_PROMPT` (`app/prompts/templates.py:365,389,465`) | code/prompts | Standard obligations. Injected LLM provider; only service importing `app.config` — inverted | llm/export |
| Refiner multi-pass polish | `app/services/refiner.py:76` (`refine_resume`), `:524` (`inject_keywords`, LLM), `:290` (`validate_master_alignment`, deterministic) | code | Standard obligations. Multi-responsibility orchestration decomposed across matching/alignment | alignment |
| Before/after comparison | `app/services/ats.py:171` (`compute_ats_score`), `app/services/refiner.py:641` (`calculate_keyword_match`) | code | Standard obligations. Deterministic pre/post scoring; adapted to return structured delta | matching + ats |

---

## Ported Files — `packages/schemas` (RIT-T-0006)

> Concrete resume-kit files that port/adapt upstream schema material. Each source and test
> file below carries the modified-source marker comment block (upstream path + pinned SHA
> `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc`). Domain models only; upstream HTTP/DB DTOs
> (`ResumeUploadResponse`, `ResumeFetchResponse`, `ResumeListResponse`, `JobUploadRequest/Response`,
> config/API-key/health/status/tracker/interview-prep DTOs, response wrappers) were **not** ported.

| resume-kit file | Upstream source | Ported/adapted material | Modification note |
|---|---|---|---|
| `packages/schemas/src/resume_kit_schemas/_coercion.py` | `app/schemas/models.py:10-127` | `_extract_text_fragments`, `_coerce_text`, `_coerce_optional_text`, `_split_description_lines`, `_coerce_string_list`, `_coerce_description_styles`, `_align_description_styles` | Extracted verbatim-in-behavior into a standalone helper module; made public; no HTTP/DB coupling |
| `packages/schemas/src/resume_kit_schemas/resume.py` | `app/schemas/models.py:129-423` | `SectionType`, `PersonalInfo`, `Experience`, `Education`, `Project`, `AdditionalInfo`, `SectionMeta`, `CustomSectionItem`, `CustomSection`, `DEFAULT_SECTION_META`, `normalize_resume_data`, `ResumeData` | Domain models split from HTTP/DB DTOs; re-namespaced; `str, Enum`→`StrEnum`; coercion moved to `_coercion`; validators/defaults/`descriptionStyles` alignment preserved; canonical `ResumeDocument`/`Contact`/`Skill` added |
| `packages/schemas/src/resume_kit_schemas/change.py` | `app/schemas/models.py:545-575,896-928` | `ResumeChange`→`ChangeProposal`, `ResumeFieldDiff`→`Diff`, `ResumeDiffSummary`, `ImproveDiffResult`→`ChangeSet` | Ported out of DTO file; list-`original`-only-for-reorder validator preserved; enriched `ChangeSet` with diffs/summary/warnings; no request/resume/job ids |
| `packages/schemas/src/resume_kit_schemas/analysis.py` | `app/schemas/refinement.py`; `app/schemas/models.py:577-616` | `RefinementConfig`, `KeywordGapAnalysis`, `AlignmentViolation`, `AlignmentReport`, `RefinementStats`, `ATSSubScores`, `ATSScore` | Ported schema-only primitives; dropped API `RefinementResult.to_stats` helper; bounds/defaults preserved; New `AnalysisReport` umbrella added |
| `packages/schemas/tests/test_characterization_resume.py` | `app/tests/unit/test_description_styles.py` | description/style coercion + alignment + default-filling characterization | Retargeted to canonical names; extended coverage to lock ported validators |
| `packages/schemas/tests/test_characterization_change.py` | `app/schemas/models.py` (`ResumeChange`); `app/tests/unit/test_resume_diff.py` | list-`original`-only-for-reorder + Diff field expectations | Characterization of ported change/diff validators |
| `packages/schemas/tests/test_characterization_analysis.py` | `app/schemas/refinement.py`; `app/schemas/models.py:577-616` | 0-100 / 1-5 bounds + defaults of refinement/ATS schemas | Characterization of ported score bounds |

Note: `job.py`, `evidence.py`, `provenance.py`, and `common.py` are **New** subsystems (candidate
evidence, claim provenance, structured warnings/artifacts, structured job description) with no
upstream material to attribute; their tests (`test_new_models.py`) are original.

---

## Ported Files — `packages/document-parser` (RIT-I-0003)

> Concrete resume-kit files that port/adapt upstream parser material. Each source file below
> carries the modified-source marker comment block (upstream path + pinned SHA
> `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc`). All modifications invert app-level dependencies:
> no file imports `app.*`, `litellm`, `openai`, or any concrete LLM provider directly.

| resume-kit file | Upstream source | Ported/adapted material | Modification note |
|---|---|---|---|
| `packages/document-parser/src/resume_kit_document_parser/dates.py` | `app/services/parser.py` (lines 35, 40: `restore_dates_from_markdown`, `_extract_markdown_dates`, `_MD_DATE_RE`) | Pure-regex date-restoration helpers | Extracted into a standalone module; no HTTP, LLM, markitdown, or `app.*` coupling; `logger` changed from module singleton to `logging.getLogger(__name__)`; behavior preserved exactly (characterization tests lock upstream regex behavior) |
| `packages/document-parser/src/resume_kit_document_parser/text_extraction.py` | `app/services/parser.py` (line 119: `parse_document`) | MarkItDown PDF/DOCX→Markdown extraction | Wrapped in a pydantic result model (`ExtractionResult`) carrying warnings; `app.*` imports removed; logging preserved via stdlib; DOCX/PDF/text dispatch logic unchanged |
| `packages/document-parser/src/resume_kit_document_parser/json_helpers.py` | `app/llm.py` (lines 218–352: `_extract_message_text`, `_to_code_block`, JSON-fence parsing helpers) | Pure response-text and JSON-fence parsing helpers | Isolated from LiteLLM/network coupling; safety constants and `parse_response_json()` entry-point added; no `app.*`, `litellm`, or provider imports |
| `packages/document-parser/src/resume_kit_document_parser/prompts.py` | `app/prompts/templates.py` (lines 21–94: `PARSE_RESUME_PROMPT`, `RESUME_SCHEMA_EXAMPLE`) | LLM prompt constants for resume parsing | Extracted as standalone pure-string constants; all other templates (improve, diff, cover-letter) deliberately omitted; no `app.*` or LLM coupling |
| `packages/document-parser/src/resume_kit_document_parser/structured.py` | `app/services/parser.py` (line 144: `parse_resume_to_json`) | Provider-injected structured resume parsing pipeline | `app.llm` / `app.prompts` / `app.schemas` / config-singleton coupling removed; LLM call goes through injected `StructuredCompletionProvider` Protocol; text extraction delegated to `extract_resume_text`; failures mapped to core warnings + reduced confidence rather than raised exceptions; result returned as `ParseResult` with warnings + provenance |

Note: characterization tests under `packages/document-parser/tests/` lock the upstream behavior of the ported helpers (date-regex patterns, JSON-fence extraction, text dispatch logic) without importing any `app.*` module.

---

## Ported Files — `packages/matching`, `packages/ats`, `packages/job-parser` (RIT-I-0004)

> Concrete resume-kit files that port/adapt upstream material into the matching, ats, and
> job-parser packages. Each file below carries the modified-source marker comment block
> (upstream path + pinned SHA `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc`, Apache-2.0).
> All modifications invert app-level dependencies: no file imports `app.*`, `litellm`,
> `openai`, or any concrete LLM provider directly.

| resume-kit file | Upstream source | Ported/adapted material | Modification note |
|---|---|---|---|
| `packages/matching/src/resume_kit_matching/keywords.py` | `app/services/refiner.py` (lines 38, 56, 181, 641: `_keyword_in_text`, `_extract_jd_skill_keys`, `analyze_keyword_gaps`, `calculate_keyword_match`) | Deterministic keyword matching and gap-analysis helpers | Extracted into a standalone module; `app.schemas.*` replaced with `resume_kit_schemas`; typed overloads added for `ResumeDocument` / `JobDescription` and plain dict; LLM and async dependencies removed; all deterministic re/text logic faithfully preserved |
| `packages/matching/src/resume_kit_matching/predicates.py` | `app/tests/evals/scorers.py` (lines 152, 161: `jd_keywords_present`, `is_valid_resume`) | Deterministic resume-validation predicates | Ported `jd_keywords_present` and `is_valid_resume` only; `app.schemas.ResumeData` replaced with `resume_kit_schemas.ResumeDocument`; accepts both model instance and dict; private keyword helpers are local copies (file-disjoint from `keywords.py` by design) |
| `packages/ats/src/resume_kit_ats/engine.py` | `app/services/ats.py` (line 171: `compute_ats_score`; line 64: `_compute_skills_coverage`; line 98: `_compute_section_completeness`; line 129: `_generate_recommendations`) | ATS composite scoring engine | Adapted and extended into the richer resume-kit ATS engine; existing 2-factor keyword+skills+section score is the seed; `app.*` imports removed (confirmed zero coupling); expanded deterministic checks enrich `recommendations` without altering seed composite score contract |
| `packages/job-parser/src/resume_kit_job_parser/prompts.py` | `app/prompts/templates.py` (line 188: `EXTRACT_KEYWORDS_PROMPT`) | LLM prompt constant for job-keyword extraction | Ported `EXTRACT_KEYWORDS_PROMPT` as a pure string constant; surrounding `app.prompts` module coupling (placeholder validation, re-exports) dropped; `{job_description}` format placeholder preserved |
| `packages/job-parser/src/resume_kit_job_parser/parse.py` | `app/services/improver.py` (line 604: `extract_job_keywords`) | Provider-injected job-description parsing pipeline | Adapted `extract_job_keywords` into an async provider-injected parser; `app.llm` / `app.prompts` / `complete_json` coupling removed; raw keyword dict mapped to canonical `resume_kit_schemas.JobDescription` + `Requirement` value objects; provider failures / malformed output mapped to safe raw-text fallback |

Note: `packages/matching/src/resume_kit_matching/match.py`, `selection.py`, and `comparison.py`
are **original resume-kit composition** with no upstream material ported — their module
docstrings explicitly state "Original resume-kit code." No attribution rows are required for
these files.

---

## Intentionally Excluded Subsystems (Replace / Leave Behind)

The following Resume-Matcher subsystems were reviewed during Phase 0 and intentionally
excluded from reuse. No attribution is required for these areas because no upstream material
will be ported.

| Subsystem | Upstream path(s) | Reason for exclusion |
|-----------|-----------------|----------------------|
| Application tracker / Kanban | `apps/backend/app/routers/applications.py`, `apps/backend/app/schemas/applications.py` (tracker portion), `apps/frontend/app/tracker/`, `apps/frontend/components/tracker/` | Product scope not carried forward; resume-kit has no application-tracking responsibility |
| SQLite persistence layer | `apps/backend/app/database.py`, `apps/backend/app/db_engine.py`, `apps/backend/app/models.py` | Architecture replaced; resume-kit does not use a persistent database layer |
| TinyDB migration logic | `apps/backend/app/scripts/` | One-time migration artefact; not relevant to a clean implementation |
| Existing API routers | `apps/backend/app/routers/` | HTTP layer tightly coupled to the web application; replaced by thin adapter pattern over core engine |
| Web frontend | `apps/frontend/` | Entire Next.js application excluded; resume-kit has no frontend |
| API-key persistence and settings UI | `apps/backend/app/crypto.py` (persistence path), `apps/backend/app/routers/` (settings endpoints) | Settings and credential management model not carried forward |
| Web-specific configuration system | `apps/backend/app/config.py` (web-app portions) | Replaced by explicit dependency injection; web-app config fields dropped |
| Application-specific job storage | `apps/backend/app/models.py` (Job, Application models) | resume-kit does not own job records; job-hunter integration handled at boundary |
| Full Resume-Matcher deployment model | `apps/backend/app/main.py`, `apps/frontend/`, Docker config | Not applicable; resume-kit is a library/tool package, not a standalone web application |
| Interview-preparation UI and service | `apps/backend/app/services/interview_prep.py`, related routers | Feature not in resume-kit scope |
| Resume-wizard / enrichment flow | `apps/backend/app/services/resume_wizard.py`, `apps/backend/app/routers/{enrichment,resume_wizard}.py` | Web-driven interactive flow; resume-kit's human-in-loop controller is New (enhancement *prompts* are attributed via the prompt-constant rows) |
| Config cache | `apps/backend/app/config_cache.py` | Web-runtime concern; not carried forward |
| PDF/DOCX export (frontend render path) | `apps/backend/app/pdf.py` | Classified **Replace → New** in the inventory: the only export path is a headless-Chromium render of the Next.js `/print/*` page (spot-checked). Nothing reusable beyond intent, so export is rebuilt from scratch with no upstream material ported — hence no attribution row |

**New subsystems** (agent plugin, MCP server, CLI, stable API contracts, freedom 0–10 policy,
human-in-the-loop controller, candidate-evidence model, claim-provenance system, approved-claim bank,
truth-validation engine, multiple-resume selection, job-hunter bridge, expanded deterministic ATS
engine, standalone no-LLM mode) have **no meaningful upstream equivalent** and therefore no material to
attribute. They are built from scratch; where a New subsystem is *seeded* by a deterministic Extract/Reuse
asset (e.g. the truth-validation engine seeded by `verify_diff_result` + eval scorers, the expanded ATS
engine seeded by `compute_ats_score`), the seed carries its own attribution row above.

---

## Per-File Attribution Comment Template

When porting any upstream file into a package under `packages/`, add the following comment
block at the top of the file (after the module docstring if one exists):

```python
# ---------------------------------------------------------------------------
# Derived from Resume-Matcher (Apache-2.0)
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Upstream path: apps/backend/app/<relative-path>
# Pinned SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc
# Modified: <one-line description of modifications, or "None — ported unchanged">
# ---------------------------------------------------------------------------
```

For adapted files with significant structural changes, use "Adapted from" instead of
"Derived from". For test files, add the comment after the module docstring and before any
imports.

---

## Reconciliation Notes

This ledger was **reconciled** against `references/reuse-inventory.md` during task RIT-T-0004
(2026-08-03). The PROVISIONAL status is removed. Actions taken:

1. **SHA/URL confirmed:** `git -C upstream rev-parse HEAD` returns
   `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc`, matching this ledger, the reuse inventory, and the
   upstream audit.
2. **Full coverage:** every subsystem classified Reuse, Extract, or Adapt in the inventory now has a
   corresponding row above, grouped by class and using the inventory's subsystem names, line-anchored
   upstream paths, and target packages.
3. **Path corrections:** the provisional "Structural resume evaluators" row incorrectly cited
   `services/ats.py`; the inventory locates the structural evaluators in
   `services/improver.py::verify_diff_result` and `tests/evals/scorers.py`. These were re-pointed, and
   ATS scoring (`services/ats.py`) is now its own **Adapt** row. Prompt attribution was split so pure
   prompt *constants* are an Extract row while prompt *adaptations* (improvement, truthfulness,
   cover-letter, skill-target, keyword) are Adapt rows, matching the inventory.
4. **Stale rows removed/merged:** the provisional standalone "Diff path parsing and resolution" and
   "Diff application and rejection reporting" rows were merged into the inventory's single "Diff
   application engine" + "Malformed/unsupported change rejection" rows. The provisional "Unit and
   service test fixtures" row was dropped as a separate entry — the inventory attributes tests with the
   code they cover (e.g. eval scorers), not as a blanket fixtures row.
5. **Replace/New kept out:** PDF/DOCX export (Replace→New) moved to the Intentionally Excluded section;
   all New subsystems noted there as having no upstream material to attribute.
6. **Spot-check:** three inventory rows (ATS engine, diff application engine, PDF export) were opened
   against real upstream files and confirmed — see the "Reviewer Spot-Check" section in
   `references/upstream-audit.md`.
