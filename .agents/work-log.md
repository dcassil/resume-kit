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
| 6 | claude/opus | RIT-T-0006 (schemas) | `packages/schemas/`,`references/attribution.md` | in-progress |
| 6 | claude/sonnet | RIT-T-0007 (core) | `packages/core/` | in-progress |
