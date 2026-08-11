# Work log — RIT-I-0023 Composable resume flows

Orchestrator worktree: `../.worktrees/rit-i-0023`, branch `feat/rit-i-0023-composable-flows`.
Integration branch: `main` (merged --no-ff by orchestrator at close).
Execution model: strictly **serial** codex waves (each task blocked_by the prior).

Gate recipe (orchestrator only, once per wave):
`uv sync --all-packages --reinstall-package resume-kit` then
`uv run --no-sync ruff check ...` / `mypy ...` / `pytest ...`.

## Waves

| Task | Title | Agent | Files (claim) | Status |
|------|-------|-------|---------------|--------|
| RIT-T-0169 | T1 durable full-resume learning seed + no-custom policy | codex opus/high | packages/evidence, packages/facade, packages/scoring, tests | DONE (commit 0d9d0d4; ruff/mypy clean, 4127 passed, 2 pre-existing failures) |
| RIT-T-0170 | T2 Flow 1 prepare-base-resume | codex opus | cli/mcp/api surfaces + parity + skill + slug test + README | DONE (commit ad1a58f; ruff/mypy clean, 4128 passed + plugin 8 passed) |
| RIT-T-0171 | T3 Flow 2 ingest-job | codex sonnet | ingest-job skill + slug test + README | DONE (commit 00e95f9; ruff clean, plugin 8 passed) |
| RIT-T-0172 | T4 Flow 3 tailor-resume | codex opus | tailor-resume skill (extract resume-workflow steps 5-10) + slug test + README | IN PROGRESS |

NOTE: plugin markdown tests are NOT in default pytest (testpaths=tests,packages).
Gate MUST also run `uv run --no-sync pytest plugins/resume-intelligence/tests/` each wave.
| RIT-T-0172 | T4 Flow 3 tailor-resume | codex | plugins skills | BLOCKED on T3 |
| RIT-T-0173 | T5 Flow 4 finalize-resume | codex | plugins skills | BLOCKED on T4 |
| RIT-T-0174 | T6 complete flow + docs/tests close-out | codex | resume-workflow, README, slug tests | BLOCKED on T2-T5 |

Serial chain → only one worker in flight at a time; no file-claim collisions.
