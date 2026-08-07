# Implementation task: RIT-T-0137 — build_structure + ProjectConfig lineage + canonical→BuildDoc projection

You are an implementing agent with ZERO prior context. Read the files named below before writing.
You WRITE FILES ONLY. Do NOT run git. Do NOT run `uv sync`, `pytest`, `ruff`, or `mypy` — the
orchestrator owns all verification and git. Create/edit source + test files only.

CRITICAL CONSTRAINT: this is ADDITIVE. You must NOT change `base`, the ingest boundary, or the
faithfulness contract. The ONLY permitted change to the existing pipeline is `build_standard`'s
input RESOLUTION (one line + a projection call). `build_standard`'s wording logic stays untouched.

## Working root
Running with `--cd` at the repo worktree root. Paths below are relative to it.

## REQUIRED READING
1. `.metis/strategies/NULL/initiatives/RIT-I-0019/tasks/RIT-T-0137.md` — task + acceptance criteria + file claims.
2. `.metis/strategies/NULL/initiatives/RIT-I-0019/initiative.md` — Detailed Design → "Standardize bridge (REQ-009)" + "Config lineage (REQ-008)".
3. `packages/facade/src/resume_kit_facade/baseline.py` — study `build_base` and `build_standard` CLOSELY; `build_structure` mirrors their spine (resolve → analyze → apply → gate → write → set_version). Note exactly how `build_standard` resolves its input today (you will change ONLY that resolution).
4. `packages/facade/src/resume_kit_facade/project_config.py` — study the `base`/`standard` pointer pair, `set_version`, `resolve_active_resume`, and the "derived_from without pointer = error" guard (RIT-T-0113 pattern). You mirror it for `structure`.
5. `packages/scoring/src/resume_kit_scoring/shape_analyzer.py` + `shape_fix.py` (RIT-T-0135/0136) — you call `analyze_resume_shape`, `apply_shape_transforms`, `content_ledger_ok`, `claims_preserved_across_sections`.
6. The EXISTING projection `project_scoredoc` (search `packages/scoring/src/resume_kit_scoring/` or wherever it lives — grep `def project_scoredoc`). Your new `project_builddoc_from_canonical` is the INVERSE-direction analogue and lives ALONGSIDE it. Read its purity/placement conventions.
7. `packages/schemas/src/resume_kit_schemas/canonical.py` (canonical `Resume`) and `resume.py` (`ResumeDocument`/`ResumeData`/`BuildDoc` target shape).

## What to build
1. `project_builddoc_from_canonical(resume: Resume) -> ResumeDocument` (BuildDoc) — pure,
   deterministic, no side effects. Maps canonical work[]/Achievement.text/SkillGroup back into the
   build-doc fields `standardize` consumes. Housed alongside `project_scoredoc`.
2. `ProjectConfig`: add optional `structure_resume` + `structure_derived_from` fields; extend
   `set_version` with `structure=`/`structure_derived_from=` params (same lineage guard);
   change `resolve_active_resume` order to `standard ?? structure ?? base ?? original`. Atomic
   write + unknown-key round-trip preserved.
3. `build_structure(root, *, answers=None, decisions=None) -> BuildStructureResult` in
   `baseline.py`: resolve `base ?? original`, run `analyze_resume_shape`, `apply_shape_transforms`
   with `decisions`, run BOTH gates (`content_ledger_ok` + `claims_preserved_across_sections`),
   and on pass write `<name>-structure.json` (canonical schema) + `set_version(structure=…,
   structure_derived_from=source)`. On gate failure REFUSE the write and return the report.
   Define `BuildStructureResult` mirroring the existing `BuildBaseResult`/`BuildStandardResult`.
4. Change `build_standard` input resolution ONLY: from `base ?? original` to
   `structure ?? base ?? original`, projecting the canonical structure via
   `project_builddoc_from_canonical` BEFORE its existing analyzer runs. Nothing else in
   `build_standard` changes.

## Tests
- `build_structure` writes canonical structure + sets `structure_resume`/`structure_derived_from`.
- lineage resolution honors `standard ?? structure ?? base ?? original`; a project with only
  `original`/`base` still resolves correctly (backward compat).
- `project_builddoc_from_canonical` round-trips the redundant-sections fixture into a valid BuildDoc.
- `build_standard` still produces `standard` when seeded from `structure` (parity).
- ALL EXISTING base/standard tests must still pass (do not break them).

## Hard constraints
- Additive only: no change to `base`, ingest, faithfulness, or `build_standard` wording logic.
- Backward compatible: unknown config keys round-trip; only-`original` projects work.
- mypy --strict; deterministic.
- Exclusive file claim: `packages/facade/src/resume_kit_facade/baseline.py`,
  `packages/facade/src/resume_kit_facade/project_config.py`, the projection module (add
  `project_builddoc_from_canonical`), and related tests under `packages/facade/tests/` +
  `packages/scoring/tests/`. Do NOT modify shape_analyzer.py/shape_fix.py/schemas/policy/ats.

When done, write a short summary to `.agents/report-0137.md`, or print it as your final message
if the sandbox blocks that path.
