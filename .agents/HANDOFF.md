# resume-kit — Orchestration Handoff

Copy-paste this into a fresh session to resume the autonomous build.

## ⭐ Current state (resume here)
- **Done & pushed:** Phases 0–6 (initiatives RIT-I-0001..0007; tasks RIT-T-0001..0061 all completed) — the entire vision roadmap is delivered. **SHIPPED: `resume-kit` is live on PyPI (0.1.0 + 0.1.1)** — `pip install "resume-kit[all]"` / `uv tool install "resume-kit[all]"` works. **Plugin is published + installable** via `/plugin marketplace add dcassil/resume-kit` → `/plugin install resume-intelligence@resume-kit` (currently **0.2.0**).
- **`main` is green & clean:** working tree clean; last commit `76f7e0a`. Engine gate = ruff clean, mypy --strict clean (**75 src files**), **2371 tests pass, 1 skipped** (engine unchanged since `b1d0a7d`; commits since are plugin/manifest/docs + Metis planning only).
- **Next up (awaiting go-ahead): 3 synonym-matching initiatives just created in `discovery`** (NOT decomposed/active — human-in-loop):
  - **RIT-I-0008 — Synonym-Aware Deterministic Matching (engine core)** [do FIRST]: shared normalize+Snowball-stem+curated alias lexicon in `matching`/`ats`; match `kind` (exact|stem|alias); fixes real misses (mentoring↔mentorship, ESLint/linting, k8s↔Kubernetes) without LLM. Integration points: `packages/matching/.../keywords.py` `_keyword_in_text`:44/`_normalize_skill_key`:58; `packages/ats/.../engine.py` `_keyword_in_text`:69/`_compute_skills_coverage`:82.
  - **RIT-I-0009 — Agent-Grown Alias Index (plugin)** [blocked_by 0008]: agent proposes truth-gated aliases → appends to `resume-kit/learning/synonyms.*`; engine merges project file over the seed; all surfaces honor via config.
  - **RIT-I-0010 — Terminology-Alignment Suggestions** [blocked_by 0008]: turn stem/alias provenance into truth-gated "mirror the employer's exact wording" rewrites via Phase-4 alignment+truth gates; no-match keywords stay gaps (never fabricated).
  - **Optional LLM/embeddings semantic tier: deliberately NOT created** (per Daniel).
- **Also still-open OPTIONAL Phase 7 — Deferred vision capabilities** (would be RIT-I-0011+; tasks from RIT-T-0062): cover-letter match/align, application-package audit, and 4 engine capabilities (`check-resume-consistency`, `score-resume-bullet`, `improve-resume-section`, `create-job-specific-resume`) + their facade+CLI/MCP/API/plugin/bridge adapters (each: engine fn → facade REGISTRY entry → thin adapters).
- **First thing to do on resume:** `uv sync --all-packages` then run the gate (below) to confirm green before touching anything.
- **Packages (14 + 1 integration):** engine — `schemas`, `core`, `document-parser`, `matching`, `ats`, `job-parser`, `policy`, `evidence`, `alignment`, `export`; facade — `facade`; transports — `cli`, `mcp`, `api`; integration — `integrations/job-hunter` (`resume_kit_job_hunter_bridge`). Plugin skills at `plugins/resume-intelligence/`. Umbrella dist = root `resume-kit` (vendors all 15 import pkgs; extras `[cli]/[mcp]/[api]/[all]`).

## Distribution, plugin & agent-conversion state (post-Phase-6, all shipped)
- **PyPI:** package name `resume-kit` (dcassil owns the PyPI Trusted Publisher now — configured). Publishing = push a `v*` tag → `.github/workflows/publish.yml` (OIDC, env `pypi`). Latest published = **0.1.1** (0.1.0 too). The plugin/skill changes since (0.1.2–0.2.0) are repo/plugin-only and do NOT change the PyPI package (hooks/skills live under `plugins/`, outside the vendored `resume_kit_*` trees) — no republish needed for them.
- **Console scripts** (in the umbrella wheel): `resume-tool` (CLI), `resume-kit-mcp` (stdio MCP server, `resume_kit_mcp.server:main`), `resume-kit-api` (uvicorn, `resume_kit_api.app:main`).
- **Claude plugin** (`plugins/resume-intelligence/`, marketplace at repo-root `.claude-plugin/marketplace.json`): 13 skills + the `resume-kit` MCP server (declared in `.claude-plugin/plugin.json`). A **SessionStart hook** (`hooks/hooks.json` → `bin/check-resume-kit.sh`, AUTO-loaded — do NOT reference it in plugin.json or it double-loads) warns (non-blocking) if `resume-kit-mcp` isn't on PATH; **`/resume-intelligence:setup`** command installs the package (`uv tool install "resume-kit[all]"`); `markitdown[pdf]` is ask-before-install. Bump plugin+marketplace version on any plugin change so the user's cache refreshes.
- **Two NEW agent-driven conversion skills (0.2.0)** — the agent IS the converter (no LLM provider, no `markitdown[pdf]` needed): `resume-to-json` (PDF/DOCX/MD/text → faithful `ResumeDocument`, lossless gates; saves `resume-kit/resumes/<name>-original.json`) and `job-to-json` (posting → structured `JobDescription` with requirements+keywords so **skills_coverage works no-LLM**; saves `resume-kit/jobs/<name>-original.json`). Both told to run in SUBAGENTS. All resume-consuming skills route document inputs through them.
- **Working-dir convention** (in the user's project, created on demand): `resume-kit/{config.json, resumes/<name>-original.json, jobs/<name>-original.json, working/<session-id>/resume.json, learning/<skill>.md}`. `-original.json` stays pristine; edits go in `working/`.
- **Schema gotchas baked into skills (from a real PDF conversion):** `SectionType` values are lowercase `text`/`stringList`/`itemList` (NOT enum names); `CustomSection` has NO `displayName`; `id` is a 1-based int; `RequirementKind` = `required`/`preferred`; non-ASCII punctuation (`·`, curly quotes) is a real ATS-parse warning — preserve verbatim in `-original.json`.
- **Proven end-to-end (subagents):** `resume-d.pdf` → JSON (9 roles/18 bullets/48 skills) + sample Staff-FS posting → JSON (8 req/4 pref/39 keywords) → `check-ats` = overall 78.9, keyword_match 66.7, section_completeness 100, **skills_coverage 89.1** (was 0.0 pre-job-to-json). Remaining misses (mentoring↔mentorship, linting, Kubernetes) are exactly what RIT-I-0008/0010 address.
- **Current gate command:**
  ```
  uv sync --all-packages && \
  uv run ruff check packages tests integrations plugins && \
  uv run mypy packages/core packages/schemas packages/document-parser packages/matching packages/ats packages/job-parser packages/policy packages/evidence packages/alignment packages/facade packages/cli packages/mcp packages/api packages/export integrations/job-hunter/src/resume_kit_job_hunter_bridge && \
  uv run pytest packages integrations plugins tests
  ```
  (extend lists as new packages land. NOTE: mypy counts SRC files only — 75 — because hyphenated test dirs have no `tests/__init__.py`; tests are covered by pytest+ruff. By design. The clean-venv install proof `tests/packaging/test_clean_venv_install.py` adds ~23s and skips if `uv` is absent or `RESUME_KIT_SKIP_INSTALL_TEST=1`.)
- **Interfaces architecture (Phase 5):** every transport (CLI/MCP/API/bridge) is a THIN adapter that calls the single `resume_kit_facade` capability REGISTRY (10 async capabilities returning `InterfaceResponse` via the `resume_kit_core.interface` substrate — `build_success`/`build_provider_not_configured`/`exit_code_for`/`ExitCode`). NO business rule lives in a transport (enforced by `tests/boundary/test_interface_boundaries.py` + cross-surface parity in `tests/interface/test_surface_parity.py`). Adding a capability = add engine fn → add facade capability+registry entry → each transport picks it up. LLM paths without a provider return a stable `PROVIDER_NOT_CONFIGURED` error; every surface has a no-LLM path.
- **Orchestration method that worked for Phase 4:** mixed **claude Agent-tool subagents (opus/sonnet) + codex** (`codex exec -s workspace-write`, stdin from /dev/null, background) in file-disjoint waves; orchestrator runs the full gate + commits per wave. Codex occasionally makes a stray edit to the task `.md` (duplicate header) — harmless, ignore. Lint E501 on ported prompt/rule constants: fix with implicit string concatenation (byte-preserving), never noqa/rule-suppression (global lint policy).

## The directive (from Daniel)
> Orchestrate the build. Use **codex** agents to decompose ONE Metis initiative at a time, then
> use **claude/codex** subagents (teamwork-orchestration skill) to implement the tasks. The main
> session is the ORCHESTRATOR: it owns ALL git (commits/merges/pushes), checks on background agents
> ~every 5 min for hangs, works ONE initiative at a time until all are done. Repo is a new PUBLIC
> git repo (done). Publish to npm **only if a good fit** (it is NOT — see below; target PyPI).
> When context hits ~90%, write a copy-paste handoff doc and stop.

## Where things live
- **Repo:** https://github.com/dcassil/resume-kit  (gh acct `dcassil`; npm acct `dpcassil01`)
- **Local:** /Users/danielcassil/Code/resume-kit  · integration branch `main` (orchestrator pushes directly; greenfield, not a protected legacy branch)
- **Planning:** Metis in `.metis/` (vision `RIT-V-0001`). NOTE: the `mcp__plugin_metis_metis__*` create/read tools are BROKEN this session (`Missing configuration: project_prefix`) — author docs as files + `metis sync` instead (see Known landmines + procedure). `metis list/status/transition` via CLI work.
- **Orchestration state:** `.agents/work-log.md` (wave/claim log), `.agents/decomp-RIT-I-*.json` (codex decompositions).
- **Donor:** Resume-Matcher cloned at gitignored `./upstream/`, pinned SHA `116f9cc3b00e1ac91734a6c2679bf41ea64a0edc`. Never distribute it.

## Key decisions already made
- **Python 3.12 + uv workspace**, NOT JavaScript. Distribution → **PyPI, not npm** (donor is Python; a JS rewrite throws away the reuse strategy). Recorded in `references/architectural-decisions/ADR-0001-*`. If Daniel wants an npm artifact, add a thin JS client over MCP/CLI in a later phase — core stays Python.
- Toolchain: `uv` 0.12.x (installed via brew), dev deps ruff+mypy(strict)+pytest+pytest-asyncio. Verify with `uv run ruff check packages`, `uv run mypy packages`, `uv run pytest`.
- Roadmap = vision Phases 0–6, each becomes ONE initiative, created + fully specified only when reached (conserves orchestrator context). Metis task `.md` files are populated by writing them directly from the codex decomposition JSON (frontmatter preserved).

## Orchestration procedure (repeat per initiative) — as actually run in Phases 2–3
1. **Create initiative as a FILE** (MCP create is broken): write `.metis/strategies/NULL/initiatives/RIT-I-XXXX/initiative.md` with full frontmatter (copy an existing one, e.g. RIT-I-0004) and ALL template sections populated (Metis rule). Then `metis sync` to index it. Transition discovery→design→ready→decompose via `metis transition RIT-I-XXXX <phase>`.
2. Dispatch **codex** to decompose. IMPORTANT: write the prompt to a scratch file and redirect stdin from /dev/null (codex hangs on a piped stdin otherwise), run FOREGROUND:
   ```
   codex exec --skip-git-repo-check -s read-only --output-schema <scratch>/decomp-schema.json \
     --color never "$(cat <scratch>/decomp-prompt.txt)" < /dev/null > <scratch>/decomp-out.json 2><scratch>/err.log
   ```
   Schema (recreate at `<scratch>/decomp-schema.json`): tasks[] with title, context, acceptance_criteria[], implementation_notes, verification_steps[], recommended_agent, files_touched[], depends_on[]. Ground codex with the initiative path + relevant `references/*.md` + existing package files + upstream donor line refs.
3. Save decomp to `.agents/decomp-<code>.json`. Generate Metis task `.md` files directly from the JSON (reuse `scratchpad/gen_tasks2.py` — args: `<INIT> <START-num> <decomp-path>`; maps depends_on→blocked_by short codes). Then `metis sync`.
4. Transition initiative → active (`metis transition`). Update `.agents/work-log.md`. Commit + push planning.
5. Execute in WAVES by file-disjointness (each task's `files_touched` + `depends_on`):
   - Parallel Agent-tool subagents for disjoint files (dispatch in ONE message, `run_in_background: true`).
   - Serialize tasks sharing a file; wire `__init__` exports + attribution as a LATE wave so module tasks stay file-disjoint.
   - Agent model = task's `recommended_agent` (opus/sonnet/haiku). Prompt = fully self-contained: "WRITE FILES ONLY, no git, package-local verification only", tell it exactly which files it may touch and NOT to edit `__init__`/attribution unless that IS its task.
6. On each wave completion: orchestrator runs the **full gate** (see Current state), fixes/re-dispatches if red, updates `.agents/work-log.md`, commits with the trailer, pushes `main`.
7. When all waves green → `metis transition` each task todo→active→completed and the initiative → completed. Update work-log + HANDOFF status ledger. Commit + push.
8. Next initiative.

Commit trailer (every commit):
```
Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01WpLT8iXnxtXkgRQeHFbhNj
```

## Status ledger
- **Phase 0 — Upstream Audit (RIT-I-0001): COMPLETE & pushed.** Deliverables: `references/upstream-audit.md`, `reuse-inventory.md` (Reuse/Extract/Adapt/Replace/New matrix), `attribution.md` (Apache-2.0). 530 upstream tests pass. Tasks RIT-T-0001..0004 completed.
- **Phase 1 — Clean Core & Schemas (RIT-I-0002): COMPLETE & pushed.** All 4 tasks (RIT-T-0005..0008) done.
  - `packages/schemas` (`resume_kit_schemas`): canonical Pydantic v2 domain models, split from transport DTOs; resume/change/analysis/coercion ported from upstream w/ markers+attribution; job/evidence/provenance/common new.
  - `packages/core` (`resume_kit_core`): StructuredCompletionProvider/CompletionProvider Protocols, ArtifactStore, error/warning taxonomy, InterfaceResponse[T] envelope, in-memory fakes (`resume_kit_core.testing`).
  - Boundary + integration guard tests under `tests/`. **Full gate green: ruff clean, mypy --strict clean (24 files), 284 tests pass.**
  - Gate command: `uv run ruff check packages tests && uv run mypy packages/core packages/schemas && uv run pytest`.
- **Phase 2 — Document Extraction & Parsing (RIT-I-0003): COMPLETE & pushed.** All 7 tasks (RIT-T-0009..0015) done.
  - `packages/document-parser` (`resume_kit_document_parser`): deterministic MarkItDown text extraction (`parse_document`, no-LLM `extract_resume_text` + `TextExtractionResult`), pure-regex date restoration, extracted JSON/text helpers + parse prompt constants, `ParseResult`/`ParseMethod` result models (compose core warnings/provenance + schemas), and provider-injected `parse_resume_structured(...)` behind `core.StructuredCompletionProvider` (+ `extract_resume_text_only` no-provider helper). All ported units attributed (SHA 116f9cc) + import-boundary test.
  - **Full gate green: ruff clean, mypy --strict clean (38 files), 401 tests pass.**
  - Gate command (UPDATED): `uv run ruff check packages tests && uv run mypy packages/core packages/schemas packages/document-parser && uv run pytest`. **IMPORTANT: run `uv sync --all-packages` first** — plain `uv sync` does NOT install non-root workspace members (document-parser), breaking test collection.
  - Landmine cleared / added: added `python-docx` dev dep (DOCX extraction tests now run); `json_helpers.py` is extracted+attributed but currently unused on the response path (provider Protocol returns `dict`) — retain for the real provider (Phase 5).
- **Phase 3 — Matching & Deterministic Analysis (RIT-I-0004): COMPLETE & pushed.** All 10 tasks (RIT-T-0016..0025) done. Three new packages:
  - `packages/matching` (`resume_kit_matching`): deterministic keyword match + gap → `KeywordGapAnalysis` (refiner port); `jd_keywords_present`/`is_valid_resume` predicates; explainable `check_job_match` → `JobMatchReport` (5 weighted dims summing 1.0, no-keyword-repetition-reward enforced); `select_best` (ranked, stable tie-break) → `ResumeSelectionResult`; `compare_versions` → `ResumeComparisonResult`.
  - `packages/ats` (`resume_kit_ats`): `compute_ats_score` → `ATSScore` (adapt of deterministic upstream seed, weights 0.55/0.25/0.20) + expanded deterministic checks (contact/section/date/formatting recs). No LLM, no matching import.
  - `packages/job-parser` (`resume_kit_job_parser`): `parse_job_description` (provider-injected → `JobDescription`) + `parse_job_description_text_only` no-LLM fallback.
  - schemas gained 6 explainable-scoring models (MatchDimensionScore, JobMatchReport, ResumeVariantScore, ResumeSelectionResult, ScoreDelta, ResumeComparisonResult).
  - **Full gate green: ruff clean, mypy --strict clean (59 files), 573 tests pass.**
  - Gate command (UPDATED): `uv run ruff check packages tests && uv run mypy packages/core packages/schemas packages/document-parser packages/matching packages/ats packages/job-parser && uv run pytest` (run `uv sync --all-packages` first).
  - Landmine cleared: removed empty `packages/*/tests/__init__.py` (mypy duplicate-`tests`-module collision once >1 package had one); import-boundary test files must use package-scoped names (hyphenated pkg dirs can't hold `tests/__init__.py`).
- **Phase 4 — Controlled Alignment (RIT-I-0005): COMPLETE & pushed.** All 12 tasks (RIT-T-0026..0037) done. Three new packages:
  - `packages/policy` (`resume_kit_policy`): freedom 0–10 path-policy table (`evaluate_change_policy`→`PolicyDecision`; factual fields employer/title/date/name/institution/location/metrics BLOCKED at every level incl. F10 via `is_path_blocked` running first); freedom ladder F0-1 skills→…→F8-10 +education.description; injection `sanitize_user_input`; truthfulness-rule constants; `verify_skill_target_plan` + `build_allowed_skill_target_keys` (verified/JD/evidence-backed skill gate).
  - `packages/evidence` (`resume_kit_evidence`): `build_candidate_evidence` (content-addressed stable IDs); `validate_resume_truth`→`TruthReport` across all 7 `ProvenanceStatus` (verified/supported/partially/user-confirmed/ambiguous/unsupported/contradicted); structural predicates (sections_preserved/no_fabricated_employers/personal_info_unchanged) + fabrication detection (validate_master_alignment/fix_alignment_violations).
  - `packages/alignment` (`resume_kit_alignment`): `apply_diffs` (policy+skill gated, original-match, reorder salvage, deep-copy); `calculate_resume_diff` + `verify_diff_result` (upstream parity); `generate_change_proposals`/`generate_skill_target_plan` (proposal-only behind `StructuredCompletionProvider`); `ReviewController` (pure human-in-loop state machine); **`align_resume`** (async orchestrator: generation→policy→apply→verify→diff→truth→score→review; F≥3 forces truth; UNSUPPORTED/CONTRADICTED stripped+re-verified or deferred to review; NFR-405 adversarial test proves fabricated employer + unsupported claim never reach output).
  - schemas gained 12 Phase-4 result models in `results.py` (PolicyDecision/PolicyRejection, SkillTarget(Plan/Source/Rejection), TruthReport, ReviewAction/Decision/Session, AlignmentResult).
  - **Full gate green: ruff clean, mypy --strict clean (52 src files), 963 tests pass / 1 skipped.** Every ported unit attributed (SHA `116f9cc`) + import-boundary tests per package.
- **Phase 5 — Interfaces (RIT-I-0006): COMPLETE & pushed.** All 11 tasks (RIT-T-0038..0048) done. Built with mixed claude+codex agents in 5 waves.
  - `packages/core` gained `interface.py` — the shared result substrate (`build_success`/`build_provider_not_configured`/`from_resume_kit_error`/`from_exception`/`build_needs_input`/`exit_code_for`/`ExitCode`) + `ErrorCode.PROVIDER_NOT_CONFIGURED`.
  - `packages/facade` (`resume_kit_facade`): 10 async capabilities + `REGISTRY` + request models + `CapabilityOptions(no_llm,strict,human_in_loop,provider)` — the single point every transport calls. Align surfaces human-in-loop questions in the envelope here.
  - `packages/cli` (`resume-tool`, Typer, 10 commands, json/text/md, exit codes via `exit_code_for`); `packages/mcp` (official `mcp` SDK, 10 stable tools, direct handler registry); `packages/api` (FastAPI, 10 POST endpoints, envelope-derived HTTP status); `plugins/resume-intelligence/` (10 SKILL.md); `integrations/job-hunter/` (`resume_kit_job_hunter_bridge`: analyze/align/validate/build + sync wrappers, no state mutation).
  - Boundary tests enforce NFR-502/503 (engine↛interface, transport frameworks engine-forbidden, engine pyproject↛transport deps, openai/anthropic forbidden everywhere). Cross-surface parity tests prove facade≡CLI≡MCP≡API. Heavy deps (typer/mcp/fastapi/uvicorn/httpx) isolated to their transport package.
  - **Full gate green: ruff clean, mypy --strict clean (69 src files), 1971 tests pass / 1 skipped.**
- **Phase 6 — Export & Packaging (RIT-I-0007): COMPLETE & pushed.** All 13 tasks (RIT-T-0049..0061) done, mixed claude+codex agents in 6 waves. SCOPED (human decision) to Export + Packaging; the rest of vision Phase 6 → optional Phase 7.
  - `packages/export` (`resume_kit_export`): deterministic no-frontend renderers — `render_pdf` (ReportLab Platypus, `rl_config.invariant` for byte-stability), `render_docx` (python-docx, fixed core-props + zip-entry rewrite), `render(resume, format, options)` dispatcher, `ExportFormat`/`ExportOptions`/`mime_type`. reportlab+python-docx confined to this package (boundary-enforced).
  - `export-resume` facade capability (REGISTRY=11): renders → writes bytes via injected `ArtifactStore` (`CapabilityOptions.artifact_store`; default in-memory) → returns `ArtifactRef` in `build_success(artifacts=[ref])`; sha256 artifact_id; deterministic; no provider needed.
  - Export adapters on all 5 surfaces: CLI `resume-tool export --format/--out`, MCP `resume_export` (base64), API `POST /export` (raw bytes + content-type), bridge `export_resume`/`_sync`, plugin `export-resume` SKILL.md. Cross-surface parity enforced.
  - **Umbrella packaging:** root `resume-kit` wheel force-includes all 15 import packages (self-contained — 0 internal `resume-kit-*` Requires-Dist), base = engine+export deps, extras `[cli]/[mcp]/[api]/[all]`, `resume-tool` console script, LICENSE/NOTICE, Trusted-Publishing `publish.yml` (tag-gated, NOT run). Clean-venv `pip install 'resume-kit[cli]'` proven end-to-end.
  - **Full gate green: ruff clean, mypy --strict clean (75 src files), 2371 tests pass / 1 skipped.**
- **Synonym-matching initiatives RIT-I-0008/0009/0010 created (in `discovery`, see the Current-state block at top).** RIT-I-0008 = deterministic synonym core (engine), 0009 = agent-grown alias index (plugin), 0010 = terminology-alignment suggestions. Do 0008 first.
- **Phase 7 (OPTIONAL): NOT STARTED.** Deferred vision Phase-6 features → a future initiative RIT-I-0011+ (tasks from RIT-T-0062):
  - Cover-letter match/align (`check-cover-letter-job-match`, `align-cover-letter`) — adapt upstream `services/cover_letter.py` behind the provider Protocol (reuse-inventory row: Adapt; only service importing `app.config` — invert it).
  - Application-package audit (`audit-application-package`) — new engine capability.
  - 4 engine capabilities: `check-resume-consistency`, `score-resume-bullet`, `improve-resume-section`, `create-job-specific-resume` (create-for-job = orchestration over align).
  - Each: engine fn → facade REGISTRY entry → thin CLI/MCP/API/plugin/bridge adapters (the Phase 5/6 pattern). Extend parity/boundary/known-slug tests accordingly.
  - Non-code: **Daniel runs the PyPI upload** (tag `v*` to trigger the Trusted-Publishing workflow, or `uv build` + `twine upload`).

## Known landmines
- **Metis tooling (this session):** the `mcp__plugin_metis_metis__*` create/read tools failed with
  `Missing configuration: project_prefix`, and `metis create initiative` rejects the `NULL` strategy
  (streamlined preset). Reliable workaround used: author the `initiative.md`/`RIT-T-*.md` files
  directly under `.metis/strategies/NULL/initiatives/RIT-I-XXXX/` with proper frontmatter, then
  `metis sync` to index them into `metis.db` (auto-recovers the short-code counters). `metis list`,
  `metis status`, and `metis transition <code> <phase>` all work fine via CLI.
- Root `pyproject.toml` `[tool.hatch.build.targets.wheel] packages = ["src/resume_kit"]` points at a dir that doesn't exist (root is a meta-package). `uv sync` tolerates it in editable mode; fix before any root `uv build` (Phase 6 packaging).
- Structured resume parsing is LLM-only upstream — no-LLM structured extraction is a known gap to design around (Phase 2).
- `improver.py` upstream was a ~1500-line mega-module — DONE: decomposed in Phase 4 into `policy` (path/skill gates, sanitizer), `alignment` (apply/diff/verify/generation/orchestrator), `evidence` (truth/fabrication).
- Export `pdf.py` depends on the upstream frontend/print-route — must be replaced, not ported (Phase 6).
