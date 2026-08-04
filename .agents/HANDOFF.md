# resume-kit — Orchestration Handoff

Copy-paste this into a fresh session to resume the autonomous build.

## ⭐ Current state (resume here)
- **Done & pushed:** Phases 0–3 (initiatives RIT-I-0001..0004; tasks RIT-T-0001..0025 all completed).
- **Next up: Phase 4 — Controlled Alignment** (create initiative RIT-I-0005; tasks continue at RIT-T-0026).
- **`main` is green & clean:** last commit `fc8893d` (close RIT-I-0004). Full gate = ruff clean, mypy --strict clean (59 files), **573 tests pass**.
- **First thing to do on resume:** `uv sync --all-packages` then run the gate (below) to confirm green before touching anything.
- **Packages so far:** `schemas`, `core`, `document-parser`, `matching`, `ats`, `job-parser`.
- **Current gate command:**
  ```
  uv sync --all-packages && \
  uv run ruff check packages tests && \
  uv run mypy packages/core packages/schemas packages/document-parser packages/matching packages/ats packages/job-parser && \
  uv run pytest
  ```
  (extend the mypy package list as new packages land each phase.)

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
  - Note: NEXT session should START at Phase 4.
- **Phases 4–6: NOT STARTED.** Next initiatives to create from vision roadmap:
  - Phase 4 — Controlled alignment (diff apply/verify engine, allowed-path policy, freedom 0-10, evidence+provenance, human-in-loop, validate-truth).
  - Phase 5 — Interfaces (CLI `resume-tool`, MCP server, agent plugin, REST API, job-hunter bridge).
  - Phase 6 — Export & package workflows (PDF/DOCX export WITHOUT the upstream Next.js frontend — `pdf.py` hard-deps Playwright+Chromium+frontend, so Replace→New; app-package audit; cover-letter match/align). Then configure PyPI publishing.

## Known landmines
- **Metis tooling (this session):** the `mcp__plugin_metis_metis__*` create/read tools failed with
  `Missing configuration: project_prefix`, and `metis create initiative` rejects the `NULL` strategy
  (streamlined preset). Reliable workaround used: author the `initiative.md`/`RIT-T-*.md` files
  directly under `.metis/strategies/NULL/initiatives/RIT-I-XXXX/` with proper frontmatter, then
  `metis sync` to index them into `metis.db` (auto-recovers the short-code counters). `metis list`,
  `metis status`, and `metis transition <code> <phase>` all work fine via CLI.
- Root `pyproject.toml` `[tool.hatch.build.targets.wheel] packages = ["src/resume_kit"]` points at a dir that doesn't exist (root is a meta-package). `uv sync` tolerates it in editable mode; fix before any root `uv build` (Phase 6 packaging).
- Structured resume parsing is LLM-only upstream — no-LLM structured extraction is a known gap to design around (Phase 2).
- `improver.py` upstream is a ~1500-line mega-module; decompose during Phase 4 extraction.
- Export `pdf.py` depends on the upstream frontend/print-route — must be replaced, not ported (Phase 6).
