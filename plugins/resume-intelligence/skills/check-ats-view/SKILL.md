---
name: check-ats-view
description: >
  Show "what the ATS sees" for a resume — the detected sections, the extracted
  entities (name/contact/links, per-role dates → computed years-of-experience,
  degrees), and the zoned keyword breakdown, exactly as an ATS parser would read
  them. Read-only: it reports, it never edits the resume. Job-INDEPENDENT (no
  keyword match, no composite score). Drives the deterministic `ats-view`
  capability (CLI `ats-view` / MCP `resume_ats_view`). No LLM required. Best run
  in a subagent.
---

# check-ats-view — the read-only "what the ATS sees" report

Surfaces the ATS-view projection of a resume (RIT-I-0017): the sections, entities,
and zoned keywords an applicant-tracking system is likely to parse. It is a
**read-only** analysis view — the counterpart to the check-* family — and it
**never edits the resume**. It is **job-independent**: it reports no keyword
coverage against a job and no composite/overall ATS score.

## Prerequisites

Run the shared **Prerequisites gate** first — see
[`../_shared/prerequisites.md`](../_shared/prerequisites.md).

- **Required input:** a **`ResumeDocument` JSON** — normally the `refine` (or
  `structure`/`base`) version once baselining has run, or the `active_resume` pointer in
  `resume-kit/config.json` (or an explicit resume JSON path the caller passes).
- **Does NOT need a job.** This view is job-independent; do not require or read a
  `JobDescription`.
- **If the resume JSON is missing** (no `active_resume`, file absent, or a raw
  PDF/DOCX where a `ResumeDocument` JSON is required): **STOP**. Do not guess and
  do not run on partial input. Tell the caller: run **`parse-resume`** first to
  produce the `ResumeDocument` JSON, then re-run this skill.

## What it does

Runs the deterministic `ats-view` capability, which projects a **ScoreDoc** for
the resume and returns an `AtsViewReport`. Present it as "here is what an ATS
parser sees in your resume":

- **Detected sections** — the canonical sections segmented from the resume, in
  order, each with its keyword **zone**.
- **Extracted entities** — name / contact / links, each role's title / company /
  dates and the **total years of experience** computed from them, and degrees.
- **Zoned keyword breakdown** — the detected keyword tokens grouped by ScoreDoc
  zone (e.g. `summary`, `experience`, `skills_list`, `education`).

**Years-of-experience is computed against a reference date.** For roles with an
open end date ("Present"), pass the caller-supplied date via `--now` so YoE is
deterministic; when omitted the capability uses a fixed default.

## How to invoke

**CLI**

```
resume-tool ats-view --resume <resume.json> [--now <YYYY-MM-DD>] [--output {json,text,md}]
```

**MCP tool:** `resume_ats_view`. Input fields: `resume` (required) and
`reference_date` (optional ISO `YYYY-MM-DD`). There is no `job` and no
`alias_file` — the view is job-independent and deterministic across every surface.

## Output (`AtsViewReport`)

Present the report as-is: `sections`, `entities` (including
`total_years_experience`), and `keyword_zones`. **Always surface the report's
`disclaimer`** verbatim or in plain language:

> A strong ATS/keyword match improves how reliably your resume is parsed and
> surfaced, but it does **not** guarantee that a recruiter will advance your
> application.

Do **not** present this as a score or a decision, and do **not** blend it into a
composite ATS number — it is a read-only view of what was parsed.

## Notes

- Fully deterministic; no provider needed. Introduces no per-item LLM calls, so
  output is identical across CLI/MCP/API/facade.
- Single responsibility: show the ATS view only. It never edits the resume and
  never scores it against a job — for keyword coverage run **check-keywords**, for
  structural parse issues run **check-structure**.
