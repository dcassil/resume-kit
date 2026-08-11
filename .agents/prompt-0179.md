# Task: RIT-T-0179 — analyze-best-practices resume_version parity + path leak (Option A)

You are an implementing agent in the resume-kit Python uv workspace. You WRITE CODE + TESTS ONLY.
Repo root is your CWD (a git worktree). Read `.metis/code-index.md` if present, and read the full task
doc at `.metis/backlog/bugs/RIT-T-0179.md`.

## HARD CONSTRAINTS
- **Do NOT run git.** The orchestrator owns all git.
- **Do NOT run `uv sync`, `--reinstall`, or the full suite.** You MAY run a scoped
  `uv run --no-sync pytest <your changed test>` IF quick. Never sync/reinstall.
- **No ruff/mypy config edits, no `# type: ignore`/`cast`/`Any` escape hatches.** Fix real code.
- Deterministic, provider-free (analyze-best-practices is no-LLM).

## Problem
`AnalyzeBestPracticesRequest.resume_version` (facade `packages/facade/src/resume_kit_facade/models.py`
~line 235) is documented (RIT-T-0164) as the resolved version identity — `base`/`structure`/`refine`/
`original`. But the CLI command (`packages/cli/src/resume_kit_cli/app.py` ~line 978) wires
`resume_version=resume` where `resume` is the RAW `--resume` path string. The direct/MCP/API surfaces
receive a bare `ResumeDocument` and leave `resume_version = None`. Result: surfaces disagree
(`tests/interface/test_surface_parity.py::test_core_fields_are_equivalent_across_surfaces[analyze-best-practices]`
fails) AND the CLI leaks a local filesystem path into report output.

## Fix — Option A: resolve to a canonical version label, uniformly
1. Add a small deterministic resolver that maps a resume input (a path and/or the resolved
   `ResumeDocument`) to a canonical version LABEL using the code-owned `ProjectConfig` pointers in
   `resume_kit_facade.project_config` — check `refine_resume`, `structure_resume`, `base_resume`,
   `standard_resume` (legacy), `active_resume`. Return the most specific matching label
   ("refine"/"structure"/"base"/"original") or `None` when nothing matches / no project context.
   - Match by resolving the input path relative to the project root and comparing to the pointer paths
     (normalize/realpath as the rest of the codebase does). Read `project_config.py` to use the ACTUAL
     field names and resolution helpers — do not invent fields.
2. **CLI**: replace `resume_version=resume` with the resolved label (or `None` if unmatched). Never
   stamp a raw path.
3. **Capability parity**: ensure `analyze_best_practices_capability` produces the same `resume_version`
   for direct/MCP/API when a project/root context is available; otherwise `None`. If the object
   surfaces genuinely have no path/root context in this capability, the correct uniform result is
   `None` on all four for a bare object — the KEY REQUIREMENT is that CLI stops stamping the raw path so
   all four AGREE. Prefer real resolution when a root is available; fall back to `None` consistently.
4. Do NOT touch the separate `compare-versions` pass-through at `capabilities.py` ~line 1490 (it
   legitimately forwards `request.resume_version`).

## Tests
- Make `test_core_fields_are_equivalent_across_surfaces[analyze-best-practices]` pass.
- Add a focused unit test for the resolver: a path matching `refine_resume` → `"refine"`; an unmatched
  path → `None`; no-project context → `None`.
- Confirm no raw filesystem path can appear in `BestPracticesReport.resume_version`.

## Scope guard
- Confine the behavior change to the `resume_version` stamp. Findings/provenance/schema unchanged.
- Do NOT alter scoring, other capabilities, or the compare-versions path.

When done: summarize files changed, the resolver's location/signature, and how the four surfaces now
agree on `resume_version`.
