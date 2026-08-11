# Task: RIT-T-0176 — Realize no-custom Flow 1 output (OMIT policy + dedupe skills)

You are an implementing agent in the resume-kit Python uv workspace. You WRITE CODE + SKILLS + TESTS.
Repo root is your CWD (a git worktree). Read `.metis/code-index.md` if present.

## HARD CONSTRAINTS
- **Do NOT run git.** The orchestrator owns all git.
- **Do NOT run `uv sync`, `--reinstall`, or the full suite.** You MAY run a scoped
  `uv run --no-sync pytest <your changed test>` IF quick. Never sync/reinstall.
- **No ruff/mypy config edits, no `# type: ignore`/`cast`/`Any` escape hatches.** No fabrication.

## Problem
RIT-T-0169 added `CustomHandoffPolicy.OMIT_AND_LEDGER_TO_EVIDENCE` + `handoff_custom_section_to_evidence()`
in `packages/scoring/src/resume_kit_scoring/shape_fix.py`, but the default is
`PRESERVE_IN_CANONICAL_CUSTOM` (shape_fix.py:104) and the Flow 1 `build-structure` path never passes
OMIT. So the "no-custom prepared output" premise is dormant. Also `parse-resume` tells agents to put
skills into BOTH `additional.technicalSkills` AND `customSections`, producing a duplicate Skills section
and inflated page count.

## Known locations (verify before editing)
- Shape entry: `apply_shape_transforms(source, report, decision_map, custom_handoff_policy=...)` at
  `packages/scoring/.../shape_fix.py:99`. OMIT enum at line 96; the OMIT branch already exists (line 161).
- Flow 1 build path: `build_structure(...)` at `packages/facade/.../baseline.py:218`, which calls
  `apply_shape_transforms(source, report, decision_map)` at `baseline.py:249` (NO policy passed → uses
  the PRESERVE default).
- Capability: `build_structure_capability(...)` at `packages/facade/.../capabilities.py:1432`; its
  request model is `BuildStructureRequest` in `packages/facade/.../models.py`.
- Surfaces: CLI `build-structure` in `packages/cli/.../app.py`; MCP `resume_build_structure` in
  `packages/mcp/.../tools.py`; API `POST /build-structure` in `packages/api/.../routes.py`+`models.py`.
- `parse-resume` skill: `plugins/resume-intelligence/skills/parse-resume/SKILL.md` (the dup-skills guidance).

## Deliverable A — expose the OMIT policy as an opt-in on build-structure (default unchanged)
- Add a request option to `BuildStructureRequest` — e.g. `omit_custom_sections: bool = False` (or a
  `custom_handoff_policy` field). Default MUST preserve current behavior.
- Thread it: `build_structure_capability` → `build_structure(...)` → `apply_shape_transforms(...,
  custom_handoff_policy=OMIT_AND_LEDGER_TO_EVIDENCE if omit else PRESERVE_IN_CANONICAL_CUSTOM)`.
- Surface the option on CLI (`--omit-custom-sections`), MCP, and API for parity (REQ-008). Add/extend a
  `SurfaceCase` in `tests/interface/test_surface_parity.py`.
- Confirm the content ledger records the moved content as `PRESERVED_IN_EVIDENCE` and
  `content_ledger_ok` still holds (nothing silently dropped).

## Deliverable B — Flow 1 uses OMIT
- Update `plugins/resume-intelligence/skills/prepare-base-resume/SKILL.md` so its build-structure step
  invokes build-structure with the omit option ON (this is what makes Flow 1's prepared output truly
  no-custom). Keep the ledger/evidence-preservation language accurate.

## Deliverable C — stop parse-resume duplicating skills
- Decide the canonical representation: flat `additional.technicalSkills` for ATS; if categorized
  skills are wanted, they render from a SINGLE source, NOT a duplicated `customSections` block. Update
  `parse-resume/SKILL.md` guidance so skills are not written into both places.
- If any build/export code path can still materialize both, dedupe deterministically before render.

## Deliverable D — tests
- Fixture/integration test: the exported Flow 1 prepared resume (build-structure with omit ON) has
  exactly ONE Skills section and NO custom holding section; the omitted custom content is present in
  learning/evidence; ledger accounts for it.
- Parity coverage for the new build-structure option.

## Scope guard
- Do NOT flip the GLOBAL default policy — scope OMIT to the opt-in path so non-Flow-1 structure builds
  are unchanged.
- Do NOT touch the export page-gate code (RIT-T-0175, already committed) or the doc-cleanup files owned
  by other tasks (`update-*`, `check-gaps`, `tailor-resume`, `_shared/*`). Stay in shape/facade/parse.

When done: summarize files changed, the new build-structure option name across surfaces, and the tests.
