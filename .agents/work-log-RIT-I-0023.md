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
| RIT-T-0169 | T1 durable full-resume learning seed + no-custom policy | codex opus/high | packages/evidence, packages/facade, packages/scoring, tests | IN PROGRESS |
| RIT-T-0170 | T2 Flow 1 prepare-base-resume | codex | plugins skills + thin composite | BLOCKED on T1 |
| RIT-T-0171 | T3 Flow 2 ingest-job | codex | plugins skills | BLOCKED on T2 |
| RIT-T-0172 | T4 Flow 3 tailor-resume | codex | plugins skills | BLOCKED on T3 |
| RIT-T-0173 | T5 Flow 4 finalize-resume | codex | plugins skills | BLOCKED on T4 |
| RIT-T-0174 | T6 complete flow + docs/tests close-out | codex | resume-workflow, README, slug tests | BLOCKED on T2-T5 |

Serial chain → only one worker in flight at a time; no file-claim collisions.
