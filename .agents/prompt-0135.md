# Implementation task: RIT-T-0135 — Read-only deterministic shape analyzer

You are an implementing agent with ZERO prior context. Read the files named below before writing.
You WRITE FILES ONLY. Do NOT run git. Do NOT run `uv sync`, `pytest`, `ruff`, or `mypy` — the
orchestrator owns all verification and git. Create/edit source + test files only.

## Working root
Running with `--cd` at the repo worktree root. Paths below are relative to it.

## REQUIRED READING
1. `.metis/strategies/NULL/initiatives/RIT-I-0019/tasks/RIT-T-0135.md` — your task + acceptance criteria + file claims.
2. `.metis/strategies/NULL/initiatives/RIT-I-0019/initiative.md` — Detailed Design → "Read-only analyzer (REQ-003)".
3. `packages/schemas/src/resume_kit_schemas/shape.py` and `packages/schemas/src/resume_kit_schemas/canonical.py` — the EXACT shape/canonical types you must use. Import them from `resume_kit_schemas.shape` and `resume_kit_schemas.canonical` (these are SUBMODULE imports; they are NOT re-exported at the package top level). Note the exact `ShapeFinding`/`ShapeReport`/`ShapeFindingFamily`/`SectionMapping`/`CanonicalSection` fields.
4. `packages/policy/src/resume_kit_policy/` — the `ResumeShapePolicy` landed by RIT-T-0134 (section_order, alias table, `other` fallback). Import and use it. Read how to construct the default policy.
5. `packages/matching/src/resume_kit_matching/keywords.py` — REUSE this tokenizer for token-set overlap (redundancy/duplicate detection). Do NOT write a bespoke tokenizer. Read its public tokenizing function signature.
6. `packages/schemas/src/resume_kit_schemas/resume.py` — the INPUT resume shape the analyzer reads (the existing `ResumeDocument`/`ResumeData` with `personalInfo`/`workExperience`/`customSections`/`additional`). The analyzer inspects THIS build-doc shape (not the canonical Resume) and reports how it diverges from canonical. Read its fields (especially `customSections`, `additional.technicalSkills`).
7. Existing analyzer style: skim `packages/scoring/src/resume_kit_scoring/` (e.g. base_fix.py) and `packages/scoring/tests/` for conventions.

## What to build (scope = READ-ONLY ANALYSIS; NO mutation, NO writes)
Implement `analyze_resume_shape(resume, policy) -> ShapeReport` in
`packages/scoring/src/resume_kit_scoring/shape_analyzer.py`, deterministic and side-effect-free.
Emit findings for every family (use the `ShapeFindingFamily` enum from shape.py):
- `CUSTOM_SECTION_MAPPED` — a custom section confidently maps to a canonical field (proposed
  target `CanonicalSection` + confidence), via the policy alias table.
- `CUSTOM_SECTION_UNMAPPED` — no confident mapping (→ `other`).
- `REDUNDANT_SECTION` / `DUPLICATE_SECTION_CONTENT` — two sections overlap by token-set
  (use the matching tokenizer; pick a conservative overlap threshold).
- `CANONICAL_FIELD_DUPLICATE` — a custom section duplicates a canonical field (e.g. a
  "Technical Skills" custom section vs `additional.technicalSkills`).
- `EMBEDDED_HEADING_LINE` — the first list item of a section equals the section heading/key.
- `SECTION_ORDER_VIOLATION` — observed order differs from `policy.section_order`.
- `BUDGET_INFO` — skills count / summary length etc., surfaced INFORMATIONALLY only, no fix.

Determinism: stable finding ordering (e.g. sort by family then section name); never rely on set
iteration order in output. No LLM, no network, no randomness.

Export `analyze_resume_shape` from the scoring package exports consistent with existing exports.

Unit tests under `packages/scoring/tests/` (table-driven): each finding family has ≥1 positive
and ≥1 clean case; the redundant "Core Skills" + full "Technical Skills" + "Domains & Industries"
scenario yields the expected `REDUNDANT_SECTION` / `CANONICAL_FIELD_DUPLICATE` findings; a
fully-canonical resume yields an empty/clean report.

## Hard constraints
- The analyzer MUST NOT mutate the input or write any file — it returns a `ShapeReport`.
- Reuse the matching tokenizer; do not add a new tokenizer.
- mypy --strict must pass (annotate fully). Deterministic output only.
- Exclusive file claim: `packages/scoring/src/resume_kit_scoring/shape_analyzer.py`,
  `packages/scoring/tests/test_shape_analyzer*.py`, and the scoring package export file (add
  `analyze_resume_shape`). Do not touch schemas/policy/matching/ats.

When done, write a short summary of files created/changed to `.agents/report-0135.md`
(if the sandbox blocks that path, print the summary as your final message instead).
