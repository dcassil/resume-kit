# Task: RIT-T-0175 — Wire page-budget gate into export + override contract

You are an implementing agent in the resume-kit Python uv workspace. You WRITE CODE + TESTS ONLY.
Repo root is your CWD (a git worktree). Read `.metis/code-index.md` if present.

## HARD CONSTRAINTS
- **Do NOT run git.** The orchestrator owns all git.
- **Do NOT run `uv sync`, `--reinstall`, or the full suite.** You MAY run a scoped
  `uv run --no-sync pytest <your new/changed test>` IF quick. Never sync/reinstall.
- **No ruff/mypy config edits, no `# type: ignore`/`cast`/`Any` escape hatches.** Fix real code.

## Problem
`finalize-resume` claims export enforces a rendered `max_pages` hard gate, but the facade
`export_resume` capability renders directly and never calls the page-budget check that ALREADY EXISTS.
Over-length resumes ship silently. Wire the gate in, fail closed, add an auditable override.

## Known locations (verify before editing)
- Facade `export_resume` capability: `packages/facade/src/resume_kit_facade/capabilities.py` (~line 1045).
- Page gate: `packages/export/.../page_gate.py`, function `check_page_budget(resume, shape_policy)` →
  returns an object with `.blocked` (bool) and `.pages` (int). (This is the same check the perfect/fit
  path and the RIT-I-0023 integration test use: `check_page_budget(final_resume, load_shape_policy(root))`.)
- Shape policy loader: `load_shape_policy(root)` (used elsewhere in facade/scoring).
- Export request model: in `packages/facade/.../models.py`; CLI export command in
  `packages/cli/.../app.py`; MCP `resume_export` in `packages/mcp/.../tools.py`; API `POST /export` in
  `packages/api/.../routes.py` + `models.py`. Study how the existing `build-structure` / `fit` hard
  gates return a failed report and how the CLI maps that to a non-zero exit (`_run_gate` / ExitCode).

## Acceptance criteria
1. `export_resume` resolves the shape policy, renders, and runs `check_page_budget`. When `.blocked`
   is true and no override is set, it FAILS CLOSED: a failed result/report and a non-zero CLI exit
   consistent with other hard gates. Include the rendered page count + max in the message.
2. Add an override: `allow_over_length: bool = False` on the export request model, a
   `--allow-over-length` CLI flag, and the equivalent MCP/API param. When true, export proceeds AND
   the result RECORDS that the override was used (auditable), ideally with the page count.
3. Behavior is consistent across direct/CLI/MCP/API. Add/extend a `SurfaceCase` (or the export case) in
   `tests/interface/test_surface_parity.py`.
4. Regression test: an over-length fixture resume fails export by default and succeeds with the
   override (place near existing export tests, e.g. `packages/export/tests` or `packages/facade/tests`).

## Scope guard
- Reuse `check_page_budget`; do NOT reimplement page counting or touch the renderer output.
- Default MUST be fail-closed so the `finalize-resume` doc claim becomes truthful.
- Do NOT touch the Flow 1 shape/parse path (that is a separate task) — stay in the export path.

When done: summarize files changed, the new override param name across surfaces, and the tests added.
