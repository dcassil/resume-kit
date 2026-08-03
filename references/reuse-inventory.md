# Reuse Inventory — Resume-Matcher

> Phase 0 deliverable (RIT-T-0003). Evidence-grounded Reuse / Extract / Adapt / Replace / New
> classification matrix. One row per relevant Resume-Matcher subsystem plus explicit confirmation
> or refutation of every candidate named in the vision. Paths are relative to
> `upstream/apps/backend/` unless noted. This file records audit evidence; it is not a design doc.

## Pinned upstream

| Field | Value |
|-------|-------|
| Upstream | https://github.com/srbhr/Resume-Matcher (Apache-2.0) |
| Pinned full commit SHA | `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc` (verified via `git -C upstream rev-parse HEAD`) |
| Audit date | 2026-08-03 |

Every row below is pinned to this single SHA. No row uses a different commit, so the SHA is stated
once here rather than repeated per row (inventory-level SHA policy, per RIT-T-0003 verification step 1).

## Taxonomy

| Class | Meaning |
|-------|---------|
| **Reuse** | Behavior is mostly correct and low-coupled; port largely unchanged (port tests with it). |
| **Extract** | Useful behavior that must be *moved* out of `app.*` into an independent package with minimal behavioral change (mainly dependency inversion at the LLM/config boundary). |
| **Adapt** | Underlying implementation is valuable but needs a new API, new boundaries, or new behavior (e.g. freedom levels, provenance, explicit provider injection) before it fits resume-kit. |
| **Replace** | Upstream implementation is unsuitable for a library/MCP/CLI product and should not be carried forward (web app, persistence, routers, UI concerns). |
| **New** | No meaningful upstream equivalent; resume-kit builds it from scratch. |

### Coupling reality check (contradicts some vision assumptions)

Direct inspection of `from app.*` imports shows the *core services* are far less coupled to the web
app than the vision's "imports heavily from `app`" warning implied. The services import only from
four `app.*` namespaces, all of which are themselves extraction/adapt targets:

- `app.llm` (LLM transport — Adapt behind a provider Protocol),
- `app.prompts.*` (pure string constants — Extract),
- `app.schemas` / `app.schemas.models` / `app.schemas.refinement` (Pydantic models — Extract),
- `app.config` (`load_config_file`, only `cover_letter.py` — Adapt).

**No core service imports `app.database`, `app.models`, `app.db_engine`, or any router.** The DB
and frontend coupling lives entirely in `main.py`, `routers/*`, `models.py`, `database.py`,
`db_engine.py`, and `pdf.py`. Therefore every core algorithm below **runs without a DB and without
a frontend** once the four `app.*` boundaries above are inverted.

Two further findings that revise the preliminary audit:

- **ATS scoring is deterministic and has zero `app.*` imports and zero LLM calls.** `services/ats.py`
  (`compute_ats_score`, `_compute_skills_coverage`, `_compute_section_completeness`) is pure Python
  (`re` + weights). The audit's "Likely LiteLLM" guess for `ats.py` is **refuted**.
- **Structural truth evaluators already exist as pure functions** in `tests/evals/scorers.py`
  (`sections_preserved`, `no_fabricated_employers`, `personal_info_unchanged`, `jd_keywords_present`,
  `is_valid_resume`) *and* in `services/improver.py::verify_diff_result` (production path). These are
  strong reusable, no-LLM assets.

---

## Matrix

Columns: subsystem | behavior | upstream path(s) | class | target package | key deps/imports | app.* coupling | upstream tests/fixtures | no DB+frontend? | no-LLM? | notes/blockers

### Strong reusable / Extract (deterministic, low-coupled)

| Subsystem | Behavior | Upstream path(s) | Class | Target pkg | Key deps | app.* coupling | Upstream tests | No DB+FE? | No-LLM? | Notes/blockers |
|---|---|---|---|---|---|---|---|---|---|---|
| MarkItDown PDF/DOCX→Markdown extraction | `parse_document(bytes,filename)` writes temp file, runs `MarkItDown().convert` | `services/parser.py:119` | **Reuse** | document-parser | `markitdown[docx]`, `pdfminer.six` | none in this fn | `tests/unit/test_parser.py` | Yes | **Yes** (pure text extraction) | CONFIRMED strong reusable. Deterministic; the only non-LLM half of parser. |
| Date restoration (month re-hydration) | `restore_dates_from_markdown` / `_extract_markdown_dates`: regex-recovers month-inclusive dates the LLM dropped, patches year-only fields | `services/parser.py:35,40` | **Reuse** | document-parser | `re` only | none | `tests/unit/test_parser.py` (`_has_month_in_dates` also `improver.py:630`) | Yes | **Yes** | CONFIRMED. Pure regex; independent of LLM path. Prime port. |
| Diff application engine (allowed paths + gates) | `apply_diffs` — Gate1 allowed-whitelist, Gate2 blocked-path, path-found, original-match, action validity; returns (result, applied, rejected) | `services/improver.py:226` (`_ALLOWED_PATH_PATTERNS:80`, `_BLOCKED_PATH_PREFIXES:94`, `_BLOCKED_FIELD_NAMES:101`, `_is_path_allowed:118`, `_is_path_blocked:123`) | **Extract** | alignment + policy | `re`; `ResumeChange` schema | `app.schemas.models` only | `tests/unit/test_apply_diffs.py` | Yes | **Yes** | CONFIRMED whitelisted paths + blocked fields (name/employer/title/date/institution/location) + rejection of malformed/unsupported changes, all as pure code. Split path-policy → `policy`, application → `alignment`. |
| Blocked fields | `_BLOCKED_FIELD_NAMES` frozenset (company/employer/title/name/date/institution/location leaves rejected) + `_BLOCKED_PATH_PREFIXES` | `services/improver.py:94,101` | **Extract** | policy | `re` | `app.schemas` | `test_apply_diffs.py` | Yes | **Yes** | CONFIRMED. Generalize into freedom-aware policy table. |
| Original-value verification | `_verify_original_matches(actual, expected)` — rejects change if stated original ≠ actual resume value | `services/improver.py:215` | **Extract** | alignment | — | none | `test_apply_diffs.py` | Yes | **Yes** | CONFIRMED. |
| Skill-addition gates | `add_skill` action gated by `_build_allowed_skill_target_keys` / `verify_skill_target_plan`; rejects unverified/duplicate skills; reorder salvage drops unverified skills | `services/improver.py:376,709,754`; `refiner.py::validate_master_alignment:290` | **Extract**/Adapt | policy + alignment | `re` | `app.schemas` | `test_verify_diffs.py`, `service/test_improver.py` | Yes | **Yes** (gate logic); planning needs LLM | CONFIRMED skill-addition gate. `verify_skill_target_plan` deterministic; `generate_skill_target_plan` is LLM (Adapt). |
| Malformed / unsupported change rejection | Reject branches in `apply_diffs` (unknown action, replace-with-nonstring, append-to-nonlist, empty value) | `services/improver.py:289–408` | **Extract** | alignment | — | `app.schemas` | `test_apply_diffs.py`, `test_resume_diff.py:47` | Yes | **Yes** | CONFIRMED. |
| Omitted-content preservation | Reorder salvage appends model-omitted originals; `_preserve_personal_info` restores dropped personal info | `services/improver.py:335–363`; `_check_for_truncation:59` | **Extract** | alignment | — | `app.schemas` | `test_apply_diffs.py` | Yes | **Yes** | CONFIRMED preservation of omitted original content. |
| Structural / diff verifier (truthfulness checks) | `verify_diff_result`: warns on dropped work/education/projects, company/title/institution changes, word-count explosion, invented %/$ metrics | `services/improver.py:430` | **Extract** | alignment + evidence | `re` | `app.schemas.models` | `tests/unit/test_verify_diffs.py` (18 asserts) | Yes | **Yes** | CONFIRMED structural evaluators — deterministic truthfulness guardrail. |
| Structural resume evaluators (eval scorers) | `sections_preserved`, `no_fabricated_employers`, `personal_info_unchanged`, `jd_keywords_present`, `is_valid_resume` | `tests/evals/scorers.py:100,117,138,152,161` | **Reuse** | tests/characterization + evidence | pure | none | `tests/evals/test_scorers.py` | Yes | **Yes** | CONFIRMED. Port as reusable validation predicates, not just tests. |
| Structured diff computation | `calculate_resume_diff` — strict field-level diff (skills add/remove case-insensitive, order-ignored, certs, summary, experience/education/project entries) | `services/improver.py:1224` | **Extract** | alignment | — | `app.schemas` | `tests/unit/test_resume_diff.py` (~25 tests) | Yes | **Yes** | CONFIRMED diff modification model, deterministic. |
| Deterministic keyword match / gap analysis | `analyze_keyword_gaps`, `calculate_keyword_match`, `_keyword_in_text`, `_extract_jd_skill_keys` | `services/refiner.py:181,641,38,56` | **Extract**/Adapt | matching | `re` | `app.schemas.refinement` | `test_refiner.py` | Yes | **Yes** | CONFIRMED. Whole-term keyword matching + injectable/non-injectable split is deterministic; useful matching substrate. |
| ATS scoring engine | `compute_ats_score` — skills coverage + section completeness, weighted, with recommendations | `services/ats.py:171` (`_compute_skills_coverage:64`, `_compute_section_completeness:98`, `_generate_recommendations:129`) | **Adapt** | ats | `re` | **none** | (exercised via `test_resume_api`/pipeline) | Yes | **Yes** | REFUTES audit "Likely LiteLLM": fully deterministic, zero app imports. Adapt (not Reuse) because vision wants a much richer ATS engine; this is a solid seed. |
| Pydantic domain schemas | `ResumeData`, `PersonalInfo`, `Experience`, `Education`, `Project`, `AdditionalInfo`, `CustomSection`, `ResumeChange`, `ResumeFieldDiff`, `ResumeDiffSummary`, `ImproveDiffResult` | `schemas/models.py:140–923` | **Extract** | schemas | Pydantic | self-contained | used across unit tests | Yes | **Yes** | CONFIRMED strong reusable. NOTE: same file mixes web request/response DTOs (see Replace row) — must split domain models from HTTP DTOs on extraction. |
| Refinement schemas | `KeywordGapAnalysis`, `AlignmentViolation`, `AlignmentReport`, `RefinementConfig`, `RefinementStats`, `RefinementResult` | `schemas/refinement.py` | **Extract** | schemas + matching | Pydantic | none | `test_refiner.py` | Yes | **Yes** | CONFIRMED. |
| Prompt-injection sanitizer | `_sanitize_user_input` redacts injection patterns (ignore/disregard/forget instructions) before user text hits the LLM | `services/improver.py:48` (`_INJECTION_PATTERNS:29`) | **Reuse** | policy/llm | `re` | none | (covered by improver tests) | Yes | **Yes** | Deterministic security guard; reusable as-is. |
| Fabrication detection & removal | `validate_master_alignment` flags skills/certs/companies absent from master (allowing verified JD skills); `fix_alignment_violations` strips critical fabrications | `services/refiner.py:290,591` | **Extract** | evidence/alignment | `re` | `app.schemas.refinement` | `test_refiner.py` | Yes | **Yes** | Deterministic truth guard; strong New-truth-engine seed. |
| AI-phrase blacklist / replacements | `AI_PHRASE_BLACKLIST`, `AI_PHRASE_REPLACEMENTS`; `remove_ai_phrases` | `prompts/refinement.py:4,71`; `refiner.py:233` | **Reuse** | alignment/policy | `re` | none | `test_refiner.py` | Yes | **Yes** | Deterministic dictionary-based scrub; useful. |
| Prompt string constants | Parse/keyword/improve/cover-letter/interview/skill-target/truthfulness prompt templates | `prompts/templates.py`, `prompts/refinement.py`, `prompts/enrichment.py`, `prompts/resume_wizard.py` | **Extract** | llm (prompt assets) | none | none | `tests/unit/test_prompt_guardrails.py` | Yes | Yes (strings) | See prompt rows below. Pure constants. |

### Adapt (valuable but needs new API/boundaries — LLM-dependent unless noted)

| Subsystem | Behavior | Upstream path(s) | Class | Target pkg | Key deps | app.* coupling | Upstream tests | No DB+FE? | No-LLM? | Notes/blockers |
|---|---|---|---|---|---|---|---|---|---|---|
| LiteLLM provider integration | `Router` with `RetryPolicy`, cooldowns, per-provider normalization (Azure Foundry/Ollama/OpenRouter), secret scrubbing | `llm.py:11,559` (`_normalize_api_base:115`, `_scrub_secrets:373`, `resolve_api_key:411`) | **Adapt** | llm | `litellm` | `app.config` | `tests/unit/test_llm.py`, `test_llm_providers.py`, `tests/integration/test_llm_contract.py` (respx) | Yes | No (is the LLM) | CONFIRMED. Adapt behind `StructuredCompletionProvider` Protocol; drop config-singleton coupling. |
| LLM config | `get_llm_config`, `get_model_name`, `get_safe_max_tokens`, `LLMConfig` | `llm.py:440,492`; `config.py` | **Adapt** | llm | pydantic-settings | `app.config` (reads `data/config.json`) | `test_settings_timeout.py`, `test_llm_providers.py` | Yes (reader only) | n/a | CONFIRMED. Replace file-singleton with injected config object. |
| JSON extraction/retry helpers | `complete`, `complete_json`, `_extract_message_text`, `_to_code_block`, JSON fence parsing | `llm.py:218–352` | **Extract**/Adapt | llm | `json`, `re` | none (pure text) | `test_llm.py` | Yes | Yes (parsing helpers alone) | Isolate text-extraction/JSON-repair helpers (pure) from transport. |
| Resume-to-JSON parsing | `parse_resume_to_json` — LLM parse → `restore_dates_from_markdown` → `ResumeData.model_validate` | `services/parser.py:144` | **Adapt** | document-parser | LLM | `app.llm`, `app.prompts`, `app.schemas` | `test_parser.py` | Yes | **No** (needs LLM for structure) | CONFIRMED. Limits no-LLM structured parsing (known vision risk). Inject provider; keep date-restore + validate deterministic wrapper. |
| Job-keyword extraction | `extract_job_keywords(job_description)` LLM→JSON of required/preferred skills, keywords | `services/improver.py:604`; prompt `EXTRACT_KEYWORDS_PROMPT` (`templates.py:188`) | **Adapt** | job-parser + matching | LLM | `app.llm`, `app.prompts` | (pipeline tests) | Yes | **No** (LLM) | CONFIRMED. Downstream match/gap analysis (refiner) is deterministic. |
| Improvement / tailoring prompts | `IMPROVE_RESUME_PROMPT_{NUDGE,KEYWORDS,FULL}`, `DIFF_IMPROVE_PROMPT`, `KEYWORD_INJECTION_PROMPT`, options/registry | `prompts/templates.py:242–363`; `prompts/refinement.py:138` | **Adapt** | llm (prompts) | none | none | `test_prompt_guardrails.py` (asserts no-invent clauses) | Yes | Yes (strings) | CONFIRMED tailoring prompts. Adapt for freedom levels. |
| Truthfulness prompts | `CRITICAL_TRUTHFULNESS_RULES_TEMPLATE` / `CRITICAL_TRUTHFULNESS_RULES` dict; no-fabrication clauses across improve/cover/interview prompts | `prompts/templates.py:211,230` | **Adapt** | policy + llm | none | none | `test_prompt_guardrails.py:34–54` | Yes | Yes (strings) | CONFIRMED. Feed resume-kit truth-validation policy. |
| Skill-target planning | `generate_skill_target_plan` (LLM) + `verify_skill_target_plan` (deterministic) + `SKILL_TARGET_PLAN_PROMPT` | `services/improver.py:839,754`; `templates.py:492` | **Adapt** | alignment | LLM | `app.llm`, `app.prompts`, `app.schemas` | `service/test_improver.py` | Yes | Planning No / verify Yes | CONFIRMED. Verifier is a deterministic gate (see Extract row); planner needs LLM. |
| Diff generation | `generate_resume_diffs`, `improve_resume`, `generate_improvements` | `services/improver.py:506,910,1474` | **Adapt** | alignment | LLM | `app.llm`, `app.prompts`, `app.schemas` | `service/test_improver.py`, `tests/integration/test_pipeline_e2e.py` | Yes | **No** (generation is LLM) | CONFIRMED. Generation LLM; verification/application deterministic (Extract rows). |
| Diff verification | `verify_diff_result`, `verify_diffs` path | `services/improver.py:430` | **Extract** | alignment | `re` | `app.schemas` | `test_verify_diffs.py` | Yes | **Yes** | CONFIRMED (also in Extract table — deterministic verifier). |
| Match scoring | `calculate_keyword_match` (refiner) + `_build_ats_score` (router) | `services/refiner.py:641`; `routers/resumes.py:462` | **Adapt** | matching + ats | `re` | refiner none; router coupled | `test_refiner.py` | refiner Yes; router No | **Yes** | CONFIRMED. Keyword match deterministic; router-side assembly is web-coupled → rebuild in `matching`. Vision wants richer explainable scoring → Adapt, audit existing before adopting. |
| Cover-letter generation | `generate_cover_letter`, `generate_outreach_message`, `generate_resume_title`; `COVER_LETTER_PROMPT`, `OUTREACH_MESSAGE_PROMPT`, `GENERATE_TITLE_PROMPT` | `services/cover_letter.py:36,90,139`; `templates.py:365,389,465` | **Adapt** | llm/export (cover-letter feature) | LLM | `app.config`, `app.llm`, `app.prompts` | (regenerate/pipeline integ tests) | Yes | **No** (LLM) | CONFIRMED. Only service importing `app.config` — invert. |
| Refiner multi-pass polish | `refine_resume` orchestration: keyword injection → AI-phrase removal → alignment check | `services/refiner.py:76`; `inject_keywords:524` (LLM), `validate_master_alignment:290` (deterministic) | **Adapt** | alignment | mixed | `app.llm`, `app.prompts.refinement`, `app.schemas.refinement` | `test_refiner.py` | Yes | Partial (injection LLM; gap analysis + alignment check no-LLM) | Multi-responsibility service (vision-flagged) — decompose. |
| PDF/DOCX export | (see Replace: only path is frontend render) | `app/pdf.py` | **Replace**→**New** | export | Playwright/Chromium + running frontend | `app.pdf` uses frontend `/print/*` | `tests/integration/test_pdf_render.py` (mocks Playwright) | **No** (needs frontend + Chromium) | Yes (render) | Export must be rebuilt without frontend dependency. See Replace row + New export note. |
| Before/after comparison | ATS/match scores computed pre and post via `compute_ats_score` + `calculate_keyword_match` | `services/ats.py:171`, `services/refiner.py:641` | **Adapt** | matching + ats | `re` | none | pipeline integ | Yes | **Yes** | CONFIRMED. Deterministic before/after is feasible. |

### Replace / Leave-behind (web-app concerns)

| Subsystem | Behavior | Upstream path(s) | Class | Target pkg | app.* coupling | Upstream tests | No DB+FE? | No-LLM? | Notes |
|---|---|---|---|---|---|---|---|---|---|
| Web frontend | Next.js app (routing, nav, state, print pages) | `apps/frontend/**` (package.json, `app/`, `components/`, `hooks/`, `lib/`, `i18n/`) | **Replace** | — (none) | n/a | frontend eslint only | No | n/a | CONFIRMED leave-behind. Not distributed. Includes navigation/state management + frontend PDF rendering (`/print/*`). |
| Application tracker / Kanban | Application status/tracker autocreate | `routers/applications.py`, `schemas/applications.py`, `models.py::Application` | **Replace** | — | full (DB+router) | `test_applications_api.py`, `test_tracker_autocreate.py` | No | n/a | CONFIRMED. `job-hunter` owns application/tracker state. |
| SQLite persistence | Async SQLAlchemy + aiosqlite schema/facade | `database.py`, `db_engine.py`, `models.py` (`Resume/Job/Improvement/Application/ApiKey`) | **Replace** | — | is the DB | `test_database.py` | No | n/a | CONFIRMED. resume-kit is stateless-library; storage behind interfaces only if ever needed. |
| TinyDB migration | One-time TinyDB→SQLite importer | `app/scripts/migrate_tinydb_to_sqlite.py` | **Replace** | — | DB | — | No | n/a | CONFIRMED. Migration compat irrelevant to a fresh product. |
| API routers | FastAPI HTTP endpoints wiring services+DB | `routers/{resumes,jobs,applications,config,enrichment,health,resume_wizard}.py`, `main.py` | **Replace** | api (rebuilt as thin adapters) | full | integration tests | No | n/a | CONFIRMED. Business logic must not live in routes; new `api` pkg is thin over core. |
| Settings / API-key persistence UI | Encrypted API-key store + config CRUD endpoints; Fernet crypto | `routers/config.py`, `config.py` (api-key fns), `config_cache.py`, `crypto.py` | **Replace** | — (crypto optional) | DB + config file | `test_config_api.py`, `test_crypto.py` | No | Yes (crypto pure) | CONFIRMED. Key *persistence/UI* replaced; `crypto.py` (Fernet, `cryptography` only) is optionally salvageable but not required for a lib. |
| Application job storage | Job records persisted for the app | `routers/jobs.py`, `models.py::Job` | **Replace** | — | DB+router | `test_jobs_api.py` | No | n/a | CONFIRMED. `job-hunter` owns job records. |
| Interview-prep UI/service | Interview prep generation (LLM) surfaced to web UI | `services/interview_prep.py`, `routers/*`, `schemas` interview models | **Replace** (feature) / Adapt (prompt) | — | `app.llm`, `app.prompts`, `app.schemas` | `test_interview_prep_service.py` | Yes (service) | No | Service itself runs headless; but it is out of resume-kit's stated scope → leave behind. Prompt guardrails reusable as evidence. |
| Resume-wizard / enrichment | Interactive wizard (analyze/enhance/regenerate descriptions) | `services/resume_wizard.py`, `services/*` via `prompts/enrichment.py`, `routers/{enrichment,resume_wizard}.py` | **Replace** (flow) | — | LLM+router | `test_resume_wizard_*`, `test_description_styles.py` | flow No | No | Web-driven interactive flow; resume-kit's human-in-loop controller is `New`. Enhancement prompts salvageable. |
| Config cache | TTL-cached config reads for web runtime | `config_cache.py` | **Replace** | — | config file | `test_settings_timeout.py` | No | Yes | CONFIRMED. Runtime concern of the web app. |
| Full deployment model | Local Next.js + FastAPI + SQLite app, startup DB init | `apps/backend/app/main.py`, docker/compose, frontend | **Replace** | — | all | e2e monitor tests | No | n/a | CONFIRMED. resume-kit ships as packages/plugin/MCP/CLI/API, not this app. |

### New (no meaningful upstream equivalent)

| Subsystem | Why new (upstream gap) | Target pkg | No DB+FE? | No-LLM? | Notes |
|---|---|---|---|---|---|
| Agent plugin package | Upstream has no agent-skill surface | plugins/resume-intelligence | Yes | Mixed | Thin adapters over core. |
| MCP server | No MCP in upstream | mcp | Yes | Mixed | Stable tool names/error codes. |
| Purpose-built CLI (`resume-tool`) | Upstream has only web API | cli | Yes | Mixed | JSON/text/md, strict + no-LLM modes. |
| Stable public API contracts | Upstream routers are app-internal, not stable contracts | api | Yes | Mixed | Thin over core. |
| Freedom 0–10 alignment policy | Upstream has fixed allowed/blocked gates only — no graduated editorial-freedom scale | policy + alignment | Yes | Yes (policy) | Builds on Extract'd path-policy + blocked fields. |
| Human-in-the-loop review controller | Upstream wizard is web-flow-specific; no headless section-by-section approve/reject/edit controller | alignment/cli/mcp | Yes | Yes (control flow) | New. |
| Candidate evidence model | No `CandidateEvidence` concept upstream | evidence | Yes | Yes | New. |
| Claim provenance system | Upstream classifies nothing (only truthfulness prompt clauses) | evidence | Yes | Yes | verified/supported/unsupported/... classes. |
| Approved-claim bank | No persistent approved-experience store upstream | evidence | Yes | Yes | New. |
| Truth-validation engine | Upstream has structural verifier (`verify_diff_result`) + prompt clauses but no unified truth-validation engine | evidence + alignment | Yes | Yes (structural) / LLM optional | Seeds: `verify_diff_result` + eval scorers. |
| Multiple-resume selection | No compare/select-best across variants upstream | matching | Yes | Yes | New. |
| `job-hunter` bridge | No such integration upstream | integrations/job-hunter | Yes | Mixed | Returns structured results; never mutates job-hunter state. |
| Deterministic ATS engine (expanded) | Upstream ATS is a narrow 2-factor score | ats | Yes | **Yes** | Extends the deterministic `compute_ats_score` seed to the vision's full ATS check list. |
| Standalone no-LLM analysis mode | Upstream requires LLM for parse/keyword/improve and has no no-LLM entrypoint | cli/api/core | Yes | **Yes** | Composed from all deterministic Extract rows (text extraction, date restore, keyword match, diff apply/verify, ATS). |

---

## Vision candidate coverage checklist

**Strong reusable — all confirmed** (with one refutation): MarkItDown extraction ✓ (Reuse),
Pydantic schemas ✓ (Extract), LLM resume→JSON parsing ✓ (Adapt — LLM-bound), date restoration ✓
(Reuse), job-keyword extraction ✓ (Adapt), tailoring prompts ✓ (Adapt), diff modification model ✓
(Extract), allowed paths ✓ (Extract), blocked fields ✓ (Extract), original-value verification ✓
(Extract), skill-addition gates ✓ (Extract/Adapt), malformed/unsupported rejection ✓ (Extract),
omitted-content preservation ✓ (Extract), LiteLLM support ✓ (Adapt), structural evaluators ✓ (Reuse,
`tests/evals/scorers.py` + `verify_diff_result`), relevant tests ✓ (unit/service/integration/eval).
**Refuted assumption:** `ats.py` is deterministic no-LLM, not LLM-backed.

**Adapt — all classified:** LiteLLM provider integration ✓, LLM config ✓, resume parsing ✓,
job-keyword extraction ✓, improvement prompts ✓, truthfulness prompts ✓, skill-target planning ✓,
diff generation ✓, diff verification ✓ (Extract), match scoring ✓, cover-letter generation ✓,
PDF/DOCX export ✓ (Replace→New), before/after comparison ✓.

**Replace/leave-behind — all covered:** web frontend ✓, tracker/Kanban ✓, SQLite persistence ✓,
TinyDB migration ✓, API routers ✓, settings/API-key UI ✓, application job storage ✓,
navigation/state ✓ (in frontend row), frontend PDF rendering ✓ (frontend + export rows),
interview-prep UI ✓, full deployment model ✓.

**New — all covered:** agent plugin ✓, MCP server ✓, CLI ✓, stable API contracts ✓, freedom 0–10 ✓,
human-in-loop controller ✓, candidate evidence ✓, claim provenance ✓, approved-claim bank ✓,
truth-validation engine ✓, multiple-resume selection ✓, job-hunter bridge ✓, deterministic ATS
engine ✓, standalone no-LLM mode ✓.

## Key blockers / surprises for downstream phases

1. **Structured parsing is LLM-only.** No deterministic resume→JSON path exists; `parse_document`
   (text) and `restore_dates_from_markdown` are the only no-LLM parser assets. No-LLM mode cannot
   produce structured `ResumeData` from a raw PDF without new deterministic extraction.
2. **`schemas/models.py` mixes domain models and HTTP DTOs** in one file — must be split on
   extraction so `schemas` package carries only canonical models.
3. **`improver.py` is a mega-module** (~1500 lines) holding path policy, diff apply, diff compute,
   verification, keyword extraction, skill planning, and orchestration — must be decomposed across
   `policy`/`alignment`/`matching`/`job-parser`.
4. **Export has a hard frontend dependency** (`pdf.py` renders the Next.js `/print/*` page via
   Playwright). Export must be rebuilt; nothing reusable beyond intent.
5. **Coupling is lighter than feared** — services import only `app.{llm,prompts,schemas,config}`,
   all invertible; no core service touches the DB or routers.

## Scope of Phase 0

Phase 0 wrote **no product code**. The only artefacts produced are the three reference documents
(`references/upstream-audit.md`, `references/reuse-inventory.md`, `references/attribution.md`). The
donor repository at `./upstream/` is a **gitignored reference clone** (`/upstream/` in `.gitignore`)
used only for read-only audit evidence — it is not distributed product code. Every classification
above is an analysis decision for later phases; no upstream material has been ported yet.

Touched only `references/reuse-inventory.md`.
