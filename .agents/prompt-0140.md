# Implementation task: RIT-T-0140 — Retire redundant ATS NONSTANDARD_SECTION finding

You are an implementing agent with ZERO prior context. Read the files named below before writing.
You WRITE FILES ONLY. Do NOT run git. Do NOT run `uv sync`, `pytest`, `ruff`, or `mypy` — the
orchestrator owns all verification and git. Create/edit source + test files only.

This is a SURGICAL cleanup. Now that the shape analyzer owns section classification, remove the
redundant `NONSTANDARD_SECTION` finding from the ATS engine. Do NOT refactor the engine; do NOT
change any other finding, gate, or the base report's output shape.

## Working root
Running with `--cd` at the repo worktree root. Paths below are relative to it.

## REQUIRED READING
1. `.metis/strategies/NULL/initiatives/RIT-I-0019/tasks/RIT-T-0140.md` — task + acceptance criteria.
2. `packages/ats/src/resume_kit_ats/engine.py` — find where `NONSTANDARD_SECTION` is emitted (grep it). Remove/neutralize ONLY that emission. Leave `_CONVENTIONAL_SECTION_KEYWORDS` and every other finding intact.
3. `grep -rn NONSTANDARD_SECTION packages` — find every test/reference. Update tests that assert it (point them at the shape analyzer's classification, or remove the stale assertion) WITHOUT weakening coverage of the remaining ATS findings.

## What to do
- Remove or guard off the `NONSTANDARD_SECTION` emission in `engine.py`.
- Update any test asserting `NONSTANDARD_SECTION` so the suite reflects that shape analysis
  (resume_kit_scoring.shape_analyzer) now owns section classification.
- Confirm `base`'s report shape and gates are otherwise unchanged (no other finding added/dropped;
  exit codes/gate behavior identical).

## Hard constraints
- Surgical only — no ATS engine refactor.
- Do NOT reintroduce a divergent copy of `_CONVENTIONAL_SECTION_KEYWORDS`.
- Do NOT weaken remaining ATS-finding coverage.
- mypy --strict must pass.
- Exclusive file claim: `packages/ats/src/resume_kit_ats/engine.py` and affected
  `packages/ats/tests/**` (plus any other test file asserting the finding). Do not modify the
  shape analyzer, facade, schemas, or policy.

When done, write a short summary to `.agents/report-0140.md`, or print it as your final message
if the sandbox blocks that path.
