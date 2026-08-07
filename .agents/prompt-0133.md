# Implementation task: RIT-T-0133 — Canonical Resume schema + shape schemas

You are an implementing agent with ZERO prior context. Read the files named below before writing.
You WRITE FILES ONLY. Do NOT run git. Do NOT run `uv sync`, `pytest`, `ruff`, or `mypy` — the
orchestrator owns all verification and git (a worker self-check tests stale vendored source and
misleads). Just create/edit the source and test files to satisfy the acceptance criteria.

## Working root
You are running with `--cd` set to the repo worktree root. All paths below are relative to it.

## REQUIRED READING (read these first, in full)
1. `.metis/strategies/NULL/initiatives/RIT-I-0019/tasks/RIT-T-0133.md` — your task, acceptance criteria, file claims.
2. `.metis/strategies/NULL/initiatives/RIT-I-0019/initiative.md` — the initiative (Detailed Design → "Canonical schema (REQ-001)" is authoritative for how content is modeled).
3. `references/jsonresume.md` — the AUTHORITATIVE canonical `Resume` definition. Transcribe THIS, faithfully. Do not invent fields not in this spec.
4. Existing schema conventions to mirror: read `packages/schemas/src/resume_kit_schemas/` (e.g. the existing `ScoreDoc` / `ResumeDocument` models and the package `__init__`/exports) so your new models match the established pydantic-v2 style, field naming, `Field(default_factory=...)` for collections, and export pattern.
5. Existing tests style: read a couple of files under `packages/schemas/tests/`.

## What to build (scope = SCHEMA ONLY; no analyzer, no canonicalizer, no facade)
Implement everything in the acceptance criteria of RIT-T-0133. Summary:

A. Canonical `Resume` pydantic-v2 models per `references/jsonresume.md`: `Resume`, `Basics`,
   `Location`, `Experience`, `Achievement`, `Metric`, `SkillGroup`, `Project`, `Education`,
   `Certification`, `Link`, `ResumeDate`, plus optional collections `awards`, `publications`,
   `volunteer`, `languages`, `interests`, `references`.
   - Enforce the spec's cardinality/`oneOrMore` rules at validation time (use
     `@model_validator(mode="after")` where cross-field): `basics.name` required; at least one of
     `email`/`phone`; `Experience.organization` + `title` required; and any other required fields
     the spec states. Violations must raise pydantic `ValidationError`.
   - `Achievement` has a required verbatim `text` field and OPTIONAL `action`, `result`,
     `metrics`, `skills`, `keywords` fields defaulting empty (the structure pass will populate
     only `text`; the rich fields exist for future work, never required).

B. A `CanonicalSection` enum whose members correspond to the canonical top-level collections
   (basics, work/experience, skills, projects, education, certifications, awards, publications,
   volunteer, languages, interests, references) PLUS an `other` fallback. This enum is the single
   source of truth and will be imported by the policy package (RIT-T-0134) — define it here.

C. Shape-pass schema types:
   - `ShapeFindingFamily` enum: `CUSTOM_SECTION_MAPPED`, `CUSTOM_SECTION_UNMAPPED`,
     `REDUNDANT_SECTION`, `DUPLICATE_SECTION_CONTENT`, `CANONICAL_FIELD_DUPLICATE`,
     `EMBEDDED_HEADING_LINE`, `SECTION_ORDER_VIOLATION`, `BUDGET_INFO` (informational).
   - `ShapeFinding` (family, code/message, section reference, optional proposed target
     `CanonicalSection` + confidence float).
   - `ShapeReport` (list[ShapeFinding] + a summary).
   - `SectionMapping` (source section name → target `CanonicalSection` + status).
   - `ContentLedgerEntry` / `ContentLedger` with per-token fate state enum
     `present_after | moved | deduped | dropped_as_heading | dropped_as_parser_artifact |
      dropped_by_explicit_decision | unresolved`.
   - `ShapeFixResult` (resulting canonical `Resume` + `ContentLedger` + applied/deferred findings).

D. Export all new public types from the package's `__init__`/exports, matching how existing
   schemas are exported.

E. Unit tests under `packages/schemas/tests/`: a valid canonical `Resume` round-trips
   (construct → `model_dump` → reconstruct); EACH cardinality rule has a failing case that raises
   `ValidationError`; `Achievement` accepts text-only; each new shape schema constructs and
   serializes.

## Hard constraints
- Do NOT add fields not present in `references/jsonresume.md` to the canonical models.
- BOUNDARY: `packages/schemas` must not import http/provider code. A boundary test scans schema
  source with a regex on lines that START with `from <word>` — never let a DOCSTRING line begin
  with the word "from". Keep imports clean.
- pydantic v2 idioms only (this repo is pydantic v2). mypy --strict must pass (annotate fully).
- Files you may create/edit (your exclusive claim): `packages/schemas/src/resume_kit_schemas/**`
  and `packages/schemas/tests/**`. Do not touch any other package.

When done, write a short summary of the files you created/changed to
`.agents/report-0133.md` (this is a normal file write, not git).
