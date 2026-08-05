# Work-log — RIT-I-0014 Deterministic ingest boundary

Orchestrator owns all git + gate + publish. Workers write files only (no git, no `uv sync`, no test runs).

Gate (orchestrator, per wave):
  uv sync --all-packages --reinstall-package resume-kit   # re-vendor CURRENT source (venv landmine)
  uv run --no-sync ruff check packages tests integrations plugins && \
  uv run --no-sync mypy <src set> && \
  uv run --no-sync pytest packages integrations plugins tests

## Waves
- Wave 1 (parallel, disjoint): RIT-T-0089 [plugins/ + setup.md + README extraction wording] ‖ RIT-T-0090 [packages: facade/cli/mcp/api + schemas + tests]
- Wave 2: RIT-T-0091 [init/set-active + config schema — facade/cli/mcp/api/core/schemas/tests/README]
- Wave 3: RIT-T-0092 [validate-faithfulness — new engine module + facade/cli/mcp/api/schemas/tests]
- Wave 4: RIT-T-0093 [skill rewrite — plugins/resume-intelligence skills]
- Wave 5: RIT-T-0094 [integration test + README + version bump]  (orchestrator)

## File claims (in-flight)
- (none yet)
