# Implementation task: RIT-T-0134 — ResumeShapePolicy in resume-kit-policy

You are an implementing agent with ZERO prior context. Read the files named below before writing.
You WRITE FILES ONLY. Do NOT run git. Do NOT run `uv sync`, `pytest`, `ruff`, or `mypy` — the
orchestrator owns all verification and git. Just create/edit source + test files.

## Working root
Running with `--cd` at the repo worktree root. Paths below are relative to it.

## REQUIRED READING
1. `.metis/strategies/NULL/initiatives/RIT-I-0019/tasks/RIT-T-0134.md` — your task + acceptance criteria + file claims.
2. `.metis/strategies/NULL/initiatives/RIT-I-0019/initiative.md` — Detailed Design → "Shape policy (REQ-002)" is authoritative.
3. `packages/schemas/src/resume_kit_schemas/canonical.py` — the canonical schema landed by RIT-T-0133. IMPORT the `CanonicalSection` enum via `from resume_kit_schemas.canonical import CanonicalSection` (canonical/shape models are exposed on the `.canonical` / `.shape` SUBMODULES, NOT re-exported at package top level — do not `from resume_kit_schemas import CanonicalSection`). It is the single source of truth; do NOT redefine it. Read its exact members.
4. `packages/policy/src/resume_kit_policy/` — read `path_policy.py` and `skill_targets.py` to mirror how policies are structured, defaulted, and overlaid from `config.json`.
5. `packages/ats/src/resume_kit_ats/engine.py` — find `_CONVENTIONAL_SECTION_KEYWORDS`; SEED your keyword→canonical alias table from it (promote the flat set into a `dict[str, CanonicalSection]`). Do NOT modify engine.py. If you copy the seed, add a comment noting the origin.
6. Existing tests: `packages/policy/tests/`.

## What to build (scope = POLICY DATA ONLY; no analysis logic)
Implement RIT-T-0134's acceptance criteria:
- `ResumeShapePolicy` in `resume_kit_policy` carrying: `section_order` (canonical ordering as
  a list of `CanonicalSection`), an alias/mapping table `dict[str, CanonicalSection]`
  (heading/keyword → canonical section, seeded from `_CONVENTIONAL_SECTION_KEYWORDS`), the
  `other` fallback behavior, and budget fields flagged INFORMATIONAL-ONLY (e.g. max skills,
  summary length) with NO trim/delete/rank affordance.
- A `default_shape_policy()` constructor and a project-overlay path that applies `config.json`
  overrides, mirroring the existing policy load/override pattern.
- Import `CanonicalSection` from `resume_kit_schemas.canonical` (do not define a second copy).
- Export the new public types from the package exports as existing policies are exported.
- Unit tests under `packages/policy/tests/`: default policy loads; alias table maps known
  headings (e.g. "Technical Skills" → skills, "Certifications" → certifications); unknown
  heading → `other`; a project override overlays the default.

## Hard constraints
- NO deletion/trim/ranking logic anywhere — this is a data table + loader only.
- Canonical section names/enum members must match `resume_kit_schemas.CanonicalSection` exactly.
- mypy --strict must pass (annotate fully). pydantic v2 / dataclass consistent with the package.
- Exclusive file claim: `packages/policy/src/resume_kit_policy/**` and `packages/policy/tests/**`.
  Do not touch schemas, ats, or any other package.

When done, write a short summary of files created/changed to `.agents/report-0134.md`.
