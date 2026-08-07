# Implementation task: RIT-T-0136 — Non-destructive canonicalizer + content ledger + two hard gates

You are an implementing agent with ZERO prior context. Read the files named below before writing.
You WRITE FILES ONLY. Do NOT run git. Do NOT run `uv sync`, `pytest`, `ruff`, or `mypy` — the
orchestrator owns all verification and git. Create/edit source + test files only.

This is the LOAD-BEARING CORRECTNESS phase. The invariant: the structure pass can move content
into canonical shape but can NEVER add, drop, reword, interpret, trim, or lose a substantive token
or a claim. Take non-destructiveness seriously — prefer marking content `unresolved` over any
lossy shortcut.

## Working root
Running with `--cd` at the repo worktree root. Paths below are relative to it.

## REQUIRED READING
1. `.metis/strategies/NULL/initiatives/RIT-I-0019/tasks/RIT-T-0136.md` — your task + acceptance criteria + file claims.
2. `.metis/strategies/NULL/initiatives/RIT-I-0019/initiative.md` — Detailed Design → "Non-destructive canonicalizer (REQ-004/005/006)" is authoritative.
3. `packages/scoring/src/resume_kit_scoring/shape_analyzer.py` (RIT-T-0135) — you CONSUME its `ShapeReport`. Read how findings are shaped.
4. `packages/schemas/src/resume_kit_schemas/shape.py` — `ContentLedger`, `ContentLedgerEntry`, `ContentFate` (states: `present_after | moved | deduped | dropped_as_heading | dropped_as_parser_artifact | dropped_by_explicit_decision | unresolved`), `ShapeFixResult`, `SectionMapping`. Import from `resume_kit_schemas.shape`.
5. `packages/schemas/src/resume_kit_schemas/canonical.py` — the canonical `Resume`/`Experience`/`Achievement`/`SkillGroup` etc. you build OUTPUT into. Import from `resume_kit_schemas.canonical`. Each source bullet → `Achievement.text` VERBATIM (leave action/result/metrics/skills/keywords empty).
6. `packages/schemas/src/resume_kit_schemas/resume.py` — the INPUT build-doc shape (`ResumeDocument`/`ResumeData`, `customSections`, `additional.technicalSkills`).
7. `packages/matching/src/resume_kit_matching/keywords.py` — REUSE this tokenizer for the ledger token accounting.
8. Existing gate/claim style: read `packages/scoring/src/resume_kit_scoring/` for the EXISTING `claims_preserved` predicate (field-scoped) — you must LEAVE IT UNCHANGED and add a NEW across-sections variant. Also read `base_fix.py` for transform conventions.

## What to build (in `packages/scoring/src/resume_kit_scoring/shape_fix.py`)
1. `apply_shape_transforms(resume, report, decisions=None) -> ShapeFixResult` — performs ONLY
   lossless moves justified by the report: map clean skill/certification/award custom sections
   into canonical fields; merge/dedupe redundant sections + canonical-field duplicates; strip
   embedded heading-line artifacts; normalize section order. Each source bullet moves VERBATIM
   into `Achievement.text`. Ambiguous/prose-heavy sections ("Core Skills" prose, "Domains &
   Industries") become `unresolved` mapping candidates OR are preserved verbatim as `other`/custom
   content — NEVER blindly coerced or dropped. An explicit `decisions` argument resolves
   `unresolved` mappings.
2. Build a `ContentLedger` recording every substantive input token's fate (one of the ContentFate
   states). `dropped_as_parser_artifact` covers known parser junk (see RIT-T-0131 symptom).
3. `content_ledger_ok(ledger) -> bool` — passes ONLY when every substantive input token is
   `present_after` or accounted for by an allowed non-lossy reason. `dropped_by_budget` is NOT a
   permitted reason at this stage (budgets belong to a later pass). An unaccounted token → fails.
4. `claims_preserved_across_sections(before, after) -> bool` (or a small report) — extracts each
   claim type (skills, employers, titles, degrees) from WHEREVER it lives in the WHOLE resume
   (not a single field) and passes iff no claim is added/dropped/altered. Moving a "Technical
   Skills" custom section into canonical `skills` must NOT read as added claims. Do NOT modify the
   existing field-scoped `claims_preserved`.

`apply_shape_transforms` itself must NOT write files — it returns a `ShapeFixResult` (new
`Resume` + ledger + applied/deferred findings). Deterministic; no LLM.

Export the new functions from the scoring package exports.

## Tests (`packages/scoring/tests/test_shape_fix*.py`) — adversarial
- A transform that drops a token FAILS `content_ledger_ok`.
- A merge that loses a skill FAILS.
- Moving a "Technical Skills" custom section into canonical `skills` PASSES
  `claims_preserved_across_sections` (the key regression).
- Each gate has ≥1 pass and ≥1 refuse case.
- Clean canonicalization of the redundant-sections fixture is fully accounted in the ledger.

## Hard constraints
- Non-destructiveness is the whole point — the ledger gate is the guard; prefer `unresolved`.
- Reuse the matching tokenizer; leave the existing `claims_preserved` untouched.
- mypy --strict must pass; deterministic output only.
- Exclusive file claim: `packages/scoring/src/resume_kit_scoring/shape_fix.py`,
  `packages/scoring/tests/test_shape_fix*.py`, and the scoring exports. Do not touch
  shape_analyzer.py, schemas, policy, matching, ats, or facade.

When done, write a short summary to `.agents/report-0136.md`, or print it as your final message
if the sandbox blocks that path.
