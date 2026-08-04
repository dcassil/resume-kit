# Work-claim log

One exclusive file claim per in-flight agent. Disjoint files → parallel; shared → serial.
Only the orchestrator edits git. Update claims as waves start and finish.

| Wave | Agent | Task | Files claimed | Status |
| ---- | ----- | ---- | ------------- | ------ |
| 1    | claude/sonnet | RIT-T-0001 | `upstream/`, `references/upstream-audit.md` | DONE (SHA 116f9cc, 530 tests pass) |
| 2    | claude/sonnet | RIT-T-0002 | `references/attribution.md` | DONE (24 provenance rows) |
| 2    | claude/opus   | RIT-T-0003 | `references/reuse-inventory.md` | DONE (~40 rows, all vision candidates classified) |
| 3    | claude/opus   | RIT-T-0004 | all 3 reference docs | DONE (reconciled, 3 rows spot-checked) |
| 4 | codex-decomp | RIT-I-0002 | Metis tasks RIT-T-0005..0008 | planned |
| 5 | claude/haiku | RIT-T-0005 (scaffold) | `pyproject.toml`,`uv.lock`,`packages/*` | DONE (uv sync+ruff+mypy green) |
| 6 | claude/opus | RIT-T-0006 (schemas) | `packages/schemas/`,`references/attribution.md` | DONE (36 tests) |
| 6 | claude/sonnet | RIT-T-0007 (core) | `packages/core/` | DONE (51 tests) |

| 7 | claude/sonnet | RIT-T-0008 (quality gates) | `tests/` | DONE (197 tests; 284 total) |

Gate (orchestrator, per wave): `uv run ruff check packages && uv run mypy packages/core && uv run mypy packages/schemas && uv run pytest`. Per-package mypy avoids the cross-package `tests` module collision.

## Phase 2 — RIT-I-0003 (Document Extraction & Parsing)

codex-decomp RIT-I-0003 → 7 tasks RIT-T-0009..0015 (`.agents/decomp-RIT-I-0003.json`).
Waves by file-disjointness (`depends_on`):
- **A**: RIT-T-0009 scaffold (`packages/document-parser/pyproject.toml`,`__init__.py`,`py.typed`) — haiku
- **B** (after A, 4 parallel, disjoint files): RIT-T-0010 dates (`dates.py`), RIT-T-0011 text-extract (`text_extraction.py`+fixtures), RIT-T-0012 json+prompts (`json_helpers.py`,`prompts.py`), RIT-T-0013 results (`results.py`) — sonnet
- **C** (after A+B): RIT-T-0014 structured adapter (`structured.py`,`__init__.py`) — opus/medium
- **D** (after B+C): RIT-T-0015 attribution + import-boundary test (`references/attribution.md`,`test_import_boundaries.py`) — sonnet

Gate (Phase 2): `uv run ruff check packages tests && uv run mypy packages/core packages/schemas packages/document-parser && uv run pytest`.

| Wave | Agent | Task | Files claimed | Status |
| ---- | ----- | ---- | ------------- | ------ |
| A | codex-decomp | RIT-I-0003 | Metis tasks RIT-T-0009..0015 | planned |
| A | claude/haiku | RIT-T-0009 (scaffold) | `packages/document-parser/{pyproject,__init__,py.typed,README}` | DONE (workspace member, imports, ruff+mypy green) |
| B | claude/sonnet | RIT-T-0010 (dates) | `dates.py`,`tests/test_dates.py`,`tests/__init__.py` | DONE (28 char tests) |
| B | claude/sonnet | RIT-T-0011 (text-extract) | `text_extraction.py`,`tests/test_text_extraction.py`,`tests/fixtures/sample_resume.md` | DONE (10 tests incl. real DOCX roundtrip) |
| B | claude/sonnet | RIT-T-0012 (json+prompts) | `json_helpers.py`,`prompts.py`,`tests/test_json_helpers.py` | DONE (30 char tests) |
| B | claude/sonnet | RIT-T-0013 (results) | `results.py`,`tests/test_results.py` | DONE (13 tests; ParseResult/ParseMethod compose core+schemas) |

| C | claude/opus | RIT-T-0014 (structured adapter) | `structured.py`,`__init__.py`,`tests/test_structured_parse.py` | DONE (6 async tests; provider-injected, no crashes on non-fatal failures) |
| D | claude/sonnet | RIT-T-0015 (attribution + boundary) | `references/attribution.md`,`tests/test_import_boundaries.py` | DONE (5 ledger rows; import-boundary test; markers all present) |

**Phase 2 (RIT-I-0003) COMPLETE.** Final gate: **401 passed**, ruff clean, mypy --strict clean (38 files). Public API of `resume_kit_document_parser`: `extract_resume_text`, `parse_resume_structured`, `extract_resume_text_only`, `ParseResult`, `ParseMethod`, `TextExtractionResult`.
Note: `json_helpers.py` extracted but not on the current response path (provider Protocol returns `dict` directly); retained as an attributed utility for the real provider in a later phase.

Orchestrator gate after Wave B: **389 passed**, ruff clean, mypy --strict clean (35 files).
Orchestrator fixes at gate: (1) updated `tests/boundary/test_boundary_no_upstream_imports.py` Phase-1-only assertion to include `document-parser`; (2) added `python-docx` dev dep so DOCX extraction tests run (un-skipped); (3) NOTE: gate must use `uv sync --all-packages` — plain `uv sync` does not install non-root workspace members.

## Phase 3 — RIT-I-0004 (Matching & Deterministic Analysis)

codex-decomp RIT-I-0004 → 10 tasks RIT-T-0016..0025 (`.agents/decomp-RIT-I-0004.json`).
Three new packages: `matching` (resume_kit_matching), `ats` (resume_kit_ats), `job-parser` (resume_kit_job_parser).
Waves by `depends_on`:
- **A**: RIT-T-0016 scaffold 3 packages — haiku
- **B** (after A, 5 parallel, disjoint): T-0017 schemas (opus/high, touches `packages/schemas`), T-0018 keyword matching (sonnet), T-0019 validation predicates (sonnet), T-0020 ATS engine (sonnet), T-0021 job-parser provider path (opus/med)
- **C** (after T-0017,0018,0020): T-0022 explainable job-match scoring (opus/med)
- **D** (after T-0022): T-0023 select-best + compare-versions (opus/med)
- **E** (after all modules): T-0024 wire public `__init__` exports (haiku) + T-0025 attribution + import-boundary tests (sonnet) — disjoint, parallel

Gate (Phase 3): `uv run ruff check packages tests && uv run mypy packages/core packages/schemas packages/document-parser packages/matching packages/ats packages/job-parser && uv run pytest` (run `uv sync --all-packages` first).

| Wave | Agent | Task | Files claimed | Status |
| ---- | ----- | ---- | ------------- | ------ |
| A | codex-decomp | RIT-I-0004 | Metis tasks RIT-T-0016..0025 | planned |
