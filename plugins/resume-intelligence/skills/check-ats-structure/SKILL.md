---
name: check-ats-structure
description: >
  Report resume-only structural / parse issues that make an ATS mis-parse,
  miss, or error on a resume — section completeness plus deterministic
  structural recommendations (contact info, missing sections, dates,
  non-ASCII / formatting risks). Resume-ONLY: needs no job and produces NO
  keyword coverage and NO composite ATS score. Drives the deterministic
  `check-ats-structure` capability (CLI `check-ats-structure` / MCP
  `resume_check_ats_structure`). No LLM required.
---

# check-ats-structure — resume-only structural / parse check

## Prerequisites

Run the shared **Prerequisites gate** first — see
[`_shared/prerequisites.md`](../_shared/prerequisites.md).

- **Required input:** a **`ResumeDocument` JSON** — the `active_resume` pointer
  in `resume-kit/config.json` (or an explicit resume JSON path the caller passes).
- **Does NOT need a job.** This check is job-independent; do not require or read
  a `JobDescription`.
- **If the resume JSON is missing** (no `active_resume`, file absent, or a raw
  PDF/DOCX where a `ResumeDocument` JSON is required): **STOP**. Do not guess and
  do not run on partial input. Tell the caller: run **`resume-to-json`** first to
  produce the `ResumeDocument` JSON, then re-run this skill.

## Purpose

Surface the structural signal a resume can be judged on **without any job**: how
complete its key sections are, and concrete, deterministic recommendations for
things that trip applicant tracking systems — missing contact fields, absent
standard sections, malformed dates, and non-ASCII / formatting parse risks.

This is deliberately **one job: structure only.** It never reports keyword
coverage, matched/missing job terms, skills coverage, or any composite/overall
ATS score — those require a job description and belong to
**`check-keyword-match`**. Keeping this skill structure-only means an agent has
exactly one obvious skill to run for "will an ATS parse this resume correctly?"

## How to invoke

Prefer the MCP tool in-process; use the CLI when scripting.

**CLI**

```
resume-tool check-ats-structure --resume <resume.json> [--output {json,text,md}] [--strict]
```

**MCP tool**: `resume_check_ats_structure`

Input field: `resume` (a serialized `ResumeDocument`). There is **no** `job` and
**no** `alias_file` — structure scoring is job-independent, so no synonym index
is involved.

## Output (`AtsStructureReport`)

| Field | Type | Notes |
|---|---|---|
| `section_completeness` | float (0–100) | How many key resume sections are present |
| `recommendations` | list of strings | Deterministic structural fixes (contact info, section presence, dates, non-ASCII / formatting risks) |

Present these two fields as-is. There is intentionally **no** `keyword_match`,
`skills_coverage`, `matched`/`missing`, or composite `overall_score` here — if
the caller wants keyword coverage against a specific job, point them at
**`check-keyword-match`**.

## Notes

- Fully deterministic. No provider needed; safe with `--no-llm` or no provider.
- Single responsibility: structure/parse readiness only. For resume↔job keyword
  coverage run **`check-keyword-match`**; for missing/injectable keywords run
  **`identify-resume-gaps`**.
- Report the recommendations verbatim; do not augment, re-score, or blend them
  into any other metric.
