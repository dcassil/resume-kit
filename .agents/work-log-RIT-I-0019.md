# Work-log — RIT-I-0019 Canonical structure pass

Orchestrator (Claude main session) owns ALL git + gate + version bump. Codex workers write files
only (no git, no `uv sync`, no pytest/ruff/mypy runs — the venv landmine makes worker self-checks
test STALE vendored source).

Worktree: `../.worktrees/rit-i-0019` on branch `feat/rit-i-0019-structure-pass`.

Gate (orchestrator, per wave):
  uv sync --all-packages --reinstall-package resume-kit   # re-vendor CURRENT source (venv landmine)
  uv run --no-sync ruff check packages tests integrations plugins
  uv run --no-sync mypy <src set>
  uv run --no-sync pytest packages integrations plugins tests

## Waves (dependency spine — mostly serial)
- Wave 1: RIT-T-0133 [packages/schemas: canonical Resume + shape schemas]  ← foundational, solo
- Wave 2: RIT-T-0134 [packages/policy: ResumeShapePolicy] (imports CanonicalSection from schemas)
- Wave 3: RIT-T-0135 [packages/scoring: shape_analyzer.py] (needs 0133+0134)
- Wave 4: RIT-T-0136 [packages/scoring: shape_fix.py + gates]
- Wave 5: RIT-T-0137 [packages/facade: build_structure + config lineage + projection]
- Wave 6: RIT-T-0138 [facade/cli/mcp/api surfaces + update-shape skill + resume-workflow]
- Wave 7: RIT-T-0139 [e2e integration test + docs + version bump]
- Wave 8: RIT-T-0140 [packages/ats: retire NONSTANDARD_SECTION] (last)

## File claims (in-flight)
- Wave 1: RIT-T-0133 → packages/schemas/** (codex)

## Status
- 2026-08-07: decomposition written (0133–0140); worktree created; Wave 1 dispatched.
