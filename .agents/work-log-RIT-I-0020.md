# Work-log — RIT-I-0020 (standardize→refine)

Orchestrator (Claude main session) owns all git + gate + merge. Codex workers write files only.
Worktree: `../.worktrees/rit-i-0020-refine` on branch `feat/rit-i-0020-refine`.
Integration: `main` (orchestrator merges `--no-ff`; RIT-I-0019 lands separately in its own worktree).

Gate (orchestrator, per wave), from worktree root:
  uv sync --all-packages --reinstall-package resume-kit
  uv run --no-sync ruff check packages tests integrations plugins
  uv run --no-sync mypy packages/*/src
  uv run --no-sync pytest packages integrations plugins tests

## Tasks
- RIT-T-0141 Phase 1 — rule reclassification + non-destructiveness guard  (structure-independent)
- RIT-T-0143 Phase 2 — whole-resume quantification elicitation            (structure-independent)
- RIT-T-0144 Phase 3 — broaden mechanical rewrite rules                   (structure-independent)
- RIT-T-0145 Phase 4 — rename standard→refine + config + input resolution (BLOCKED on RIT-I-0019)
- RIT-T-0146 Phase 5 — surfaces + skill + workflow + deprecation aliases  (BLOCKED on Phase 4)
- RIT-T-0147 Phase 6 — E2E + migration + docs + version bump              (BLOCKED on Phase 5)

## Waves (this session: Phases 1-3 only, per user)
All three edit packages/scoring/src/resume_kit_scoring/best_practices.py → SERIAL.
- Wave 1: RIT-T-0141 (codex)  → gate → commit
- Wave 2: RIT-T-0143 (codex)  → gate → commit
- Wave 3: RIT-T-0144 (codex)  → gate → commit
Then merge feat/rit-i-0020-refine → main (--no-ff), push.
Then poll every 5 min for RIT-I-0019 landing on main; on land, rebase + do Phases 4-6.

## File claims (in-flight)
- Wave 1 (RIT-T-0141): packages/scoring/.../best_practices.py, content_preservation.py,
  __init__.py; packages/facade/.../baseline.py; scoring+facade tests.

## Status
- 2026-08-07: decomposed into 6 tasks; worktree created; dispatching Wave 1.
