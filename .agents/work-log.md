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
| B | opus/high | RIT-T-0017 (schemas) | `schemas/analysis.py`,`schemas/__init__.py`,test | DONE (6 models: MatchDimensionScore/JobMatchReport/ResumeVariantScore/ResumeSelectionResult/ScoreDelta/ResumeComparisonResult; 11 tests) |
| B | sonnet | RIT-T-0018 (keyword match) | `matching/keywords.py`,char test | DONE (29 tests; whole-term matching → KeywordGapAnalysis) |
| B | sonnet | RIT-T-0019 (predicates) | `matching/predicates.py`,test | DONE (19 tests; jd_keywords_present, is_valid_resume) |
| B | sonnet | RIT-T-0020 (ATS engine) | `ats/engine.py`,2 tests | DONE (41 tests; compute_ats_score→ATSScore, weights 0.55/0.25/0.20 + expanded checks) |
| B | opus/med | RIT-T-0021 (job-parser) | `job-parser/{parse,prompts}.py`,test | DONE (6 tests; provider-injected + no-LLM fallback) |

Orchestrator gate after Wave B: **539 passed**, ruff clean, mypy --strict clean (51 files).
Gate fixes: (1) boundary test expected-set += matching/ats/job-parser; (2) removed empty `packages/*/tests/__init__.py` (4 files) — they collided as duplicate `tests` module under mypy; pytest uses `--import-mode=importlib` so they're unnecessary.
| C | opus/med | RIT-T-0022 (job-match) | `matching/match.py`,test | DONE (7 tests; 5 weighted dims sum 1.0; no-repetition-reward proven) |
| D | opus/med | RIT-T-0023 (select/compare) | `matching/selection.py`,`matching/comparison.py`,test | DONE (9 tests; stable tie-break, score deltas) |
| E | haiku | RIT-T-0024 (exports) | `matching/ats/job-parser __init__.py` | DONE (public APIs importable) |
| E | sonnet | RIT-T-0025 (attribution+boundary) | `references/attribution.md`,3× `test_*_import_boundaries.py` | DONE (5 ledger rows; boundary tests) |

**Phase 3 (RIT-I-0004) COMPLETE.** Final gate: **573 passed**, ruff clean, mypy --strict clean (59 files).
Public APIs: `resume_kit_matching`{calculate_keyword_match, analyze_keyword_gaps, jd_keywords_present, is_valid_resume, check_job_match, select_best, compare_versions}; `resume_kit_ats`{compute_ats_score}; `resume_kit_job_parser`{parse_job_description, parse_job_description_text_only}.
Note: import-boundary test files are package-scoped names (test_matching/ats/job_parser_import_boundaries.py) to avoid the mypy duplicate-module issue with hyphenated package dirs that can't hold tests/__init__.py.

---

## Phase 4 — Controlled Alignment (RIT-I-0005) — PLANNED

Codex decomposed into 12 file-disjoint tasks RIT-T-0026..0037 (`.agents/decomp-RIT-I-0005.json`).
New packages: `packages/policy` (resume_kit_policy), `packages/evidence` (resume_kit_evidence),
`packages/alignment` (resume_kit_alignment). Initiative → active.

Wave plan (by DAG / file-disjointness):
| Wave | Tasks | Notes |
| ---- | ----- | ----- |
| A | RIT-T-0026 (scaffold 3 pkgs) [opus/high] | lands first; everything depends transitively |
| B | RIT-T-0027 (schemas results.py) [opus/med] | new result types (PolicyDecision/AlignmentResult/TruthReport/ReviewSession/SkillTargetPlan) |
| C | RIT-T-0028 freedom path policy [opus/high], 0029 skill targets [opus/med], 0030 evidence predicates+fabrication [opus/med], 0033 diff+verifier [opus/med], 0035 review controller [opus/med] | all dep only on 0027; file-disjoint |
| D | RIT-T-0031 candidate evidence+truth [opus/med] (dep 0030), 0032 apply_diffs engine [opus/med] (dep 0028+0029), 0034 provider generation [opus/med] (dep 0028+0029) | file-disjoint |
| E | RIT-T-0036 align_resume orchestration [opus/high] (dep 0031,0032,0033,0034,0035) | invariant tests: NFR-405 fabricating-provider rejected, F>=3 forces truth, no unsupported claim |
| F | RIT-T-0037 exports+attribution+boundaries [sonnet/med] (dep all) | edits every __init__ + attribution.md — LATE, serial |

Gate after each wave (run `uv sync --all-packages` first):
`uv run ruff check packages tests && uv run mypy packages/core packages/schemas packages/document-parser packages/matching packages/ats packages/job-parser packages/policy packages/evidence packages/alignment && uv run pytest`

Phase 4 Wave A/B/C executed (mixed claude + codex agents):
| Wave | Task | Agent | Result |
| ---- | ---- | ----- | ------ |
| A | RIT-T-0026 scaffold | claude/opus | DONE (3 pkgs; boundary expected-set updated) |
| B | RIT-T-0027 result schemas | codex | DONE (results.py: PolicyDecision/SkillTargetPlan/TruthReport/Review*/AlignmentResult; 10 tests) |
| C | RIT-T-0028 freedom path policy | claude/opus | DONE (124 tests; factual fields blocked at F10; F0-10 ladder) |
| C | RIT-T-0029 verified skill targets | codex | DONE (11 tests; verify_skill_target_plan + build_allowed_skill_target_keys) |
| C | RIT-T-0030 evidence predicates+fabrication | claude/opus | DONE (25 tests; predicates + validate_master_alignment/fix_alignment_violations) |
| C | RIT-T-0033 diff+verifier | codex | DONE (calculate_resume_diff + verify_diff_result parity) |
| C | RIT-T-0035 review controller | claude/opus | DONE (21 tests; pure state machine, InterfaceResponse) |

Orchestrator gate after Wave C: **848 passed, 1 skipped**, ruff clean, mypy --strict clean (82 files).
Gate fixes: boundary expected-set += policy/evidence/alignment; lint cleanup in ported truthfulness.py (implicit string concat to preserve verbatim prompt text under line-length), SIM108/SIM103 in review.py/path_policy.py.

Phase 4 Wave D executed (2 claude/opus + 1 codex):
| Wave | Task | Agent | Result |
| ---- | ---- | ----- | ------ |
| D | RIT-T-0031 candidate evidence + truth | claude/opus | DONE (22 tests; build_candidate_evidence + validate_resume_truth → TruthReport across all 7 provenance statuses; content-addressed evidence IDs) |
| D | RIT-T-0032 apply diffs engine | claude/opus | DONE (35 tests; apply_diffs gated by path_policy + skill_targets; factual fields blocked at F10 via PolicyReasonCode; deep-copy, reorder salvage) |
| D | RIT-T-0034 provider proposal generation | codex | DONE (9 tests; generate_change_proposals + generate_skill_target_plan behind StructuredCompletionProvider; proposals-only, never returns final resume; sanitizes inputs) |

Orchestrator gate after Wave D: **934 passed, 1 skipped**, ruff clean, mypy --strict clean (92 files).
Gate fixes: lint E501 in ported prompt constants (prompts.py, generation.py) resolved via implicit string concatenation preserving verbatim prompt text (no rule suppression); import sorting auto-fixed.
Remaining: Wave E (RIT-T-0036 align_resume orchestration + invariant tests), Wave F (RIT-T-0037 exports/attribution/boundaries).

Phase 4 Wave E executed (claude/opus):
| Wave | Task | Agent | Result |
| ---- | ---- | ----- | ------ |
| E | RIT-T-0036 align_resume orchestration | claude/opus | DONE (94 alignment tests; async align_resume wires generation→policy→apply→verify→diff→truth→score→review; F>=3 forces truth; UNSUPPORTED/CONTRADICTED stripped + re-verified or deferred to human review; NFR-405 adversarial test proves fabricated employer + unsupported claim never reach output) |

Orchestrator gate after Wave E: **948 passed, 1 skipped**, ruff clean (first pass), mypy --strict clean (95 files).
Remaining: Wave F (RIT-T-0037 exports/attribution/import-boundaries) — final task, then close initiative.

Phase 4 Wave F executed (claude/sonnet):
| Wave | Task | Agent | Result |
| ---- | ---- | ----- | ------ |
| F | RIT-T-0037 exports + attribution + boundaries | claude/sonnet | DONE (public __all__ for schemas[+12]/policy[24]/evidence/alignment; import-boundary + public-export tests for all 3 pkgs; 15 attribution rows (11 ported+4 new)) |

**Phase 4 (RIT-I-0005) COMPLETE & pushed.** Final gate: **963 passed, 1 skipped**, ruff clean, mypy --strict clean (52 src files).
Note on mypy count: 52 = actual src .py files across all 9 packages (mypy checks src only; hyphenated test dirs have no __init__.py → covered by pytest+ruff, not directory-mypy). Earlier 92/95 counts were an artifact of empty __init__.py changing module resolution; not a coverage regression.
Public engine APIs now importable: resume_kit_alignment{align_resume, apply_diffs, calculate_resume_diff, verify_diff_result, generate_change_proposals, generate_skill_target_plan, ReviewController}; resume_kit_policy{evaluate_change_policy, verify_skill_target_plan, sanitize_user_input, freedom constants, truthfulness rules}; resume_kit_evidence{build_candidate_evidence, validate_resume_truth, structural predicates, fabrication helpers}; resume_kit_schemas{AlignmentResult, TruthReport, PolicyDecision, SkillTargetPlan, Review*}.
NEXT: Phase 5 — Interfaces (CLI resume-tool, MCP server, agent plugin, REST API, job-hunter bridge).

---

## Phase 5 — Interfaces (RIT-I-0006) — PLANNED

Codex decomposed into 11 file-disjoint tasks RIT-T-0038..0048 (`.agents/decomp-RIT-I-0006.json`).
Scope (human-decided): ALL FIVE surfaces (CLI, MCP, REST API, plugin skills, job-hunter bridge),
exposing ONLY the 10 built-engine capabilities as thin adapters. New pkgs: packages/facade,
packages/cli, packages/mcp, packages/api; plus plugins/resume-intelligence/, integrations/job-hunter/.
Stack: Typer (CLI), official mcp SDK, FastAPI+uvicorn (API) — heavy deps isolated per package (NFR-503).

Wave plan (by DAG):
| Wave | Tasks | Notes |
| ---- | ----- | ----- |
| A | RIT-T-0038 core interface substrate [opus/high] | InterfaceResponse mapping + ErrorCode taxonomy + exit-code map; blocks all |
| B | RIT-T-0039 capability facade pkg [opus/high] | uniform (request,config,provider)->InterfaceResponse over 10 engine fns; blocks transports |
| C | RIT-T-0040 scaffold cli/mcp/api [sonnet/med] | pyproject + entry points + deps |
| D | RIT-T-0041 CLI, 0042 MCP, 0043 API, 0044 bridge, 0045 plugin skills | file-disjoint parallel over facade (0044 dep 0039; others dep 0040) |
| E | RIT-T-0046 parity tests, 0047 boundary tests, 0048 exports | late; depend on transports |

INTEGRATION NOTE for orchestrator: integrations/job-hunter is NOT under packages/* — root pyproject
workspace `members` must gain "integrations/*" (and facade/cli/mcp/api are picked up by packages/*).
Bridge task (0044) or scaffold must update root workspace members + the gate mypy list.

Gate after each wave (uv sync --all-packages first):
`uv run ruff check packages tests && uv run mypy packages/core ... packages/cli packages/mcp packages/api && uv run pytest`

Phase 5 Wave D executed (3 claude/opus + 1 claude/sonnet + 1 codex):
| Wave | Task | Agent | Result |
| ---- | ---- | ----- | ------ |
| D | RIT-T-0041 resume-tool CLI | claude/opus | DONE (15 tests; Typer, 10 commands, json/text/md, exit codes via exit_code_for, --help works) |
| D | RIT-T-0042 MCP server | codex | DONE (19 tests; mcp.server.Server low-level, 10 stable tools, direct handler registry) |
| D | RIT-T-0043 FastAPI routes | claude/opus | DONE (17 tests; 10 POST endpoints, envelope-derived HTTP status, TestClient) |
| D | RIT-T-0044 job-hunter bridge | claude/opus | DONE (8 tests; analyze/align/validate/build callables + sync wrappers; no-mutation asserted) |
| D | RIT-T-0045 plugin skills | claude/sonnet | DONE (10 SKILL.md + 8 tests; guards against deferred-capability mentions) |

Orchestrator integration + gate after Wave D: **1335 passed, 1 skipped**, ruff clean, mypy --strict clean (69 files).
Orchestrator fixes: (1) added "integrations/*" to root workspace members so the bridge is gate-covered; (2) removed bridge `# type: ignore[arg-type]` — typed `_run` param as Coroutine (first-class, no suppression); (3) fixed 2 sys.modules-pollution test failures (core+facade no-transport-import tests) by running the import check in a clean subprocess; (4) MCP tools.py mypy: narrowed `_find_model_type` to `type[BaseModel]` via issubclass; (5) CLI ruff: StrEnum + PEP-695 generic.
Remaining: Wave E (RIT-T-0046 parity, 0047 boundary, 0048 exports).
