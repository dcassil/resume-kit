# Implementation task: RIT-T-0138 — Surfaces (facade/CLI/MCP/API) + update-shape skill + resume-workflow

You are an implementing agent with ZERO prior context. Read the files named below before writing.
You WRITE FILES ONLY. Do NOT run git. Do NOT run `uv sync`, `pytest`, `ruff`, or `mypy` — the
orchestrator owns all verification and git. Create/edit source + test files only.

Keep adapters THIN — all logic already lives in the facade/engine. You are surfacing existing
capabilities across CLI/MCP/API and authoring a plugin skill, plus a workflow wiring edit.

## Working root
Running with `--cd` at the repo worktree root. Paths below are relative to it.

## REQUIRED READING
1. `.metis/strategies/NULL/initiatives/RIT-I-0019/tasks/RIT-T-0138.md` — task + acceptance criteria + file claims.
2. `packages/facade/src/resume_kit_facade/baseline.py` — `build_structure` + `analyze_resume_shape` are the capabilities to surface (RIT-T-0137/0135). Find the existing facade capability wrappers for `build_base`/`build_standard`/`analyze_best_practices` and mirror them.
3. CLI: study how `build-base`/`build-structure`-style commands are registered in the CLI package (`packages/cli/src/...`) — pattern for `resume-tool analyze-shape` and `resume-tool build-structure`. Gate failure must yield a non-zero exit (find the existing `_run_gate`/exit-code helper).
4. MCP: study existing tools (e.g. `resume_build_base`, `resume_build_standard`, `resume_analyze_best_practices`) in `packages/mcp/src/...` — register `resume_analyze_shape` + `resume_build_structure` the same way.
5. API: study existing routes in `packages/api/src/...` — add the analogous shape/structure routes.
6. Cross-surface parity tests: find the existing parity test module (grep `parity`) and extend it for the new capabilities.
7. Plugin skills: read `plugins/resume-intelligence/skills/update-structure/` (template) and `plugins/resume-intelligence/skills/_shared/` (gate conventions). Read `plugins/resume-intelligence/skills/resume-workflow/` for ordering + gate phrasing.

## What to build
1. Facade capability functions for `analyze_resume_shape` and `build_structure` (consistent with
   existing capability wrappers).
2. CLI commands `resume-tool analyze-shape` and `resume-tool build-structure` (gate failure →
   non-zero exit).
3. MCP tools `resume_analyze_shape` and `resume_build_structure`.
4. API routes exposing shape analysis + structure build.
5. Cross-surface parity tests: facade/CLI/MCP/API produce identical shape reports, identical
   `structure` output, and identical lineage state for the same input.
6. `update-shape` plugin skill under `plugins/resume-intelligence/skills/` — single-responsibility,
   mirrors existing skill conventions. It drives the structure pass conversationally: runs the
   analyzer, applies auto-safe canonicalization, surfaces ambiguous section mappings for a decision
   (NEVER guesses), never removes content. State clearly: deterministic, non-destructive, no
   wording change, no budget/trim, ambiguous mappings deferred. Do NOT over-claim capability.
7. `resume-workflow`: insert the structure step AFTER `update-structure`/`base` and BEFORE the
   wording (`update-best-practices`/standard) step, with prerequisite-gating phrasing consistent
   with the existing guide.

## Hard constraints
- Adapters are thin; no business logic in CLI/MCP/API.
- Skill docs must be faithful to the deterministic, non-destructive engine (no over-claim).
- mypy --strict; parity across surfaces (assert with parity tests).
- Exclusive file claim: facade capability module(s), CLI command module(s), MCP server module,
  API routes module, the parity test module, `plugins/resume-intelligence/skills/update-shape/**`,
  and `plugins/resume-intelligence/skills/resume-workflow/**`. Do NOT modify the engine
  (shape_analyzer/shape_fix), schemas, policy, or project_config internals.

When done, write a short summary to `.agents/report-0138.md`, or print it as your final message
if the sandbox blocks that path.
