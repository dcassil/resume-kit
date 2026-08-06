---
name: check-keywords
description: >
  Check resume↔job keyword coverage — the percentage of the job's keywords the
  resume already covers, plus the matched and missing keyword lists — for a
  resume against a specific job description. Presents ONLY the keyword slice; no
  composite / overall ATS score. Honors the project synonym index
  (`alias_file`) so grown, user-confirmed aliases count. Drives the
  deterministic match capability (CLI `match` / MCP `resume_check_job_match`).
  No LLM required.
---

> **Renamed:** `check-keywords` was `check-keyword-match` before v1.0.0 (see RIT-A-0005).


# check-keywords — resume↔job keyword coverage

## Prerequisites

Run the shared **Prerequisites gate** first — see
[`_shared/prerequisites.md`](../_shared/prerequisites.md).

- **Required inputs (BOTH):**
  - a **`ResumeDocument` JSON** — the `active_resume` pointer in
    `resume-kit/config.json` (or an explicit resume JSON path the caller passes).
  - a **`JobDescription` JSON** — the `active_job` pointer in
    `resume-kit/config.json` (or an explicit job JSON path the caller passes).
- **If either is missing** (no pointer, file absent, or a raw file where a
  canonical JSON is required): **STOP**. Do not guess and do not run on partial
  input. Tell the caller exactly which is missing and name the upstream skill:
  - Missing/unconverted resume → run **`parse-resume`** first.
  - Missing/unconverted job → run **`parse-job`** first.

Conversions are best run in **subagents** (large intermediate text stays out of
the main context); pass the saved JSON paths back here.

## Purpose

Answer one question: **how much of the job's keyword set does this resume already
cover, and which specific keywords are matched vs. missing?** Use it to decide
whether a resume needs alignment before applying, or to see exactly which job
terms to address.

This is deliberately **one job: keyword coverage only.** It does not report a
composite/overall ATS score, section completeness, or structural parse issues
(that is **`check-structure`**), and it is distinct from the
missing/injectable keyword breakdown of **`check-gaps`**.

## How to invoke

Prefer the MCP tool in-process; use the CLI when scripting.

**CLI**

```
resume-tool match --resume <resume.json> --job <job.json> \
    [--alias-file <path>] [--output {json,text,md}] [--strict]
```

**MCP tool**: `resume_check_job_match`

Input fields: `resume` (serialized `ResumeDocument`), `job` (serialized
`JobDescription`), `alias_file`, `strict`.

## Honor the project synonym index

Read `resume-kit/config.json`'s `alias_file` (default
`resume-kit/learning/synonyms.json`) and pass it to this capability so the grown,
user-confirmed synonym index is honored — add `--alias-file <path>` on the CLI,
or set the `alias_file` field on the `resume_check_job_match` MCP request (the
same way **`learn-terminology`** / **`update-terminology`** thread the file through).
The engine UNIONs the project file over the seed lexicon, so a resume term
recorded as a synonym of a job keyword counts as covered on the very next run.
Scoring stays fully deterministic — no LLM.

## Output — present ONLY the keyword slice

The `match` capability returns a `JobMatchReport`. Present **only** its keyword
coverage:

| Present | Notes |
|---|---|
| keyword coverage percentage | share of the job's keywords the resume covers |
| matched keywords | job keywords the resume already covers |
| missing keywords | job keywords the resume does not yet cover |

**Do NOT** surface or blend in any composite/overall score, section
completeness, or other blended metrics the report may also carry — slice those
out. For structure use **`check-structure`**; for the missing/injectable
breakdown use **`check-gaps`**.

## After coverage: grow the synonym index (truth-gated)

After you present coverage, for each **missing** job keyword the resume plausibly
satisfies under a DIFFERENT surface term, run the shared **`learn-terminology`**
workflow: it applies the truthfulness gate (genuine same-skill synonym only —
NetSuite↔SuiteCommerce yes, React≈Vue never; never alias to make an ABSENT skill
score as present), asks the user to confirm, and only then appends a justified
`{canonical, alias, why}` entry to the alias file so the next deterministic run
counts it. Never append silently; always report exactly what was added. See the
**`learn-terminology`** skill for the full workflow and file format.

## Notes

- Fully deterministic. No provider needed; safe with `--no-llm` or no provider.
- Single responsibility: resume↔job keyword coverage. Do not augment or
  re-interpret the matched/missing lists — present them as-is.
