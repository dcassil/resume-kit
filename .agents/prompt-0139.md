# Implementation task: RIT-T-0139 — E2E original→base→structure→standard test + docs reconcile

You are an implementing agent with ZERO prior context. Read the files named below before writing.
You WRITE FILES ONLY. Do NOT run git. Do NOT run `uv sync`, `pytest`, `ruff`, or `mypy` — the
orchestrator owns all verification, git, AND the version bump. Do NOT edit any pyproject.toml or
plugin version field (the orchestrator does the version bump). Create the E2E test + a committed
fixture, and reconcile README/docs prose.

## Working root
Running with `--cd` at the repo worktree root. Paths below are relative to it.

## REQUIRED READING
1. `.metis/strategies/NULL/initiatives/RIT-I-0019/tasks/RIT-T-0139.md` — task + acceptance criteria.
2. `.metis/strategies/NULL/initiatives/RIT-I-0019/initiative.md` — Use Case 1 describes the redundant-sections fixture (Core Skills + full Technical Skills overlapping additional.technicalSkills + Domains & Industries).
3. The EXISTING baselining E2E test (grep for `build_base`/`build_standard` in `packages/facade/tests/` or `integrations/`) and the ScoreDoc E2E — model your test on these (fixture loading, artifact assertions, lineage-pointer assertions).
4. `packages/facade/src/resume_kit_facade/baseline.py` — `build_structure` / `build_standard` signatures and result types.
5. `packages/facade/src/resume_kit_facade/project_config.py` — `structure_resume` / `structure_derived_from` pointers to assert.
6. `README.md` and any docs under `docs/` describing the original→base→standard lineage.

## What to build
1. An integration test (place it beside the existing baselining E2E test) driving a real
   multi-custom-section fixture through: ingest → base → build_structure → build_standard. Assert:
   - `structure` conforms to the canonical Resume schema (validates);
   - `structure` is content-lossless vs `base` (the ContentLedger is fully accounted — no
     unaccounted substantive token; assert content_ledger_ok on the result);
   - the redundant Core Skills / Technical Skills / Domains & Industries case is merged/mapped as
     expected (canonical skills deduped; ambiguous sections deferred as unresolved, NOT dropped);
   - `build_standard` runs unchanged on the projected structure and still writes `standard`;
   - config lineage pointers structure_resume / structure_derived_from are set correctly.
2. Commit the fixture (a resume-a-like doc with the redundant/non-standard sections) under the
   appropriate test tree.
3. Reconcile README / docs prose to describe the new `structure` stage and the
   original → base → structure → standard lineage. Prose only — no behavior change.

## Hard constraints
- Do NOT modify any version field (pyproject.toml / plugin manifest) — orchestrator owns that.
- Assert structural invariants (schema conformance, ledger fully accounted, standard produced)
  rather than brittle exact strings where avoidable.
- Do NOT weaken or delete existing tests.
- Exclusive file claim: the new integration test module + committed fixture, and README/docs prose.
  Do not modify engine/facade/surface source.

When done, write a short summary to `.agents/report-0139.md`, or print it as your final message
if the sandbox blocks that path.
