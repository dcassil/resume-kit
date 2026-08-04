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
