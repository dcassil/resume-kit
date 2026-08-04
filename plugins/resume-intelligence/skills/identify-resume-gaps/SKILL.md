---
name: identify-resume-gaps
description: >
  Deterministically analyse keyword gaps between a tailored resume, a master
  resume, and a job description.  Returns injectable and non-injectable
  missing keywords.  No LLM required.
---

> **Inputs must be canonical JSON.** This capability consumes a resume as a `ResumeDocument` JSON (build it from a PDF/DOCX/MD/text file with the **resume-to-json** skill) and, where a job is involved, a `JobDescription` JSON (build it with **job-to-json** so skills-coverage scoring works). Run those conversions in **subagents**, then pass the saved JSON paths here — they live under `resume-kit/resumes/` and `resume-kit/jobs/`.

## Purpose

Produce a `KeywordGapAnalysis` showing which job keywords are missing from the
tailored resume, which can be added from the master resume (injectable), and
which are absent from both (non-injectable).

## When to use

- Before running `align-resume` to understand what gaps exist and whether they
  are addressable.
- When the user wants to see missing keywords without committing to a full
  alignment run.

## Inputs

| Field | Type | Notes |
|---|---|---|
| `job` | `JobDescription` | The target job |
| `tailored` | `ResumeDocument` | The resume version being evaluated |
| `master` | `ResumeDocument` | The full master resume used to check injectability |

**Options** (`CapabilityOptions`)

| Option | Default | Effect |
|---|---|---|
| `strict` | false | Escalate advisory warnings to failures |

`no_llm` has no effect — this capability is always deterministic.

## How to invoke

**CLI**

```
resume-tool identify-gaps --job <job.json> \
    --tailored <tailored.json> --master <master.json> \
    [--output {json,text,md}] [--strict]
```

**MCP tool**: `resume_identify_gaps`

Input fields: `job`, `tailored`, `master`, `strict`.

## Output (`InterfaceResponse`)

| Field | Type | Notes |
|---|---|---|
| `data` | `KeywordGapAnalysis` | `current_match_percentage`, `injectable_keywords`, `non_injectable_keywords` |
| `warnings` | list | Advisory issues |
| `errors` | list | Failures |
| `requiresHumanInput` | bool | Always false |
| `questions` | list | Always empty |
| `provenance` | object | Source attribution |

## Honor the project synonym index

Read `resume-kit/config.json`'s `alias_file` (default
`resume-kit/learning/synonyms.json`) and pass it to this capability so the
grown, user-confirmed synonym index is honored: add `--alias-file <path>` on the
CLI, or set the `alias_file` field on the `resume_identify_gaps` MCP request. The
engine UNIONs the project file over the seed lexicon; scoring stays fully
deterministic (no LLM).

## After analysis: grow the synonym index (truth-gated)

After you report the gap analysis, for each missing job keyword that the resume
plausibly satisfies under a DIFFERENT surface term, run the shared
**`manage-synonyms`** workflow: it applies the truthfulness gate (genuine
same-skill synonym only — NetSuite↔SuiteCommerce yes, React≈Vue never; never
alias to make an ABSENT skill score as present), asks the user to confirm, and
only then appends a justified `{canonical, alias, why}` entry to the alias file
so the next deterministic run matches it. Do not confuse this with
`non_injectable_keywords`: a genuinely absent skill is a real gap and must NOT be
aliased away. Never append silently; always report exactly what was added. See
the `manage-synonyms` skill for the full workflow and file format.

## Gaps vs. terminology mirrors

A **gap** is a JD keyword absent from the resume — surface it here, never rewrite
it in. Distinct from a **terminology mirror**, where the resume already satisfies
the JD keyword under a different surface form (an alias hit); mirroring the
employer's exact wording is truthful and is handled by the **`align-terminology`**
skill. Keep the two apart: a real gap must NOT be aliased or mirrored away.

## Notes

- Fully deterministic.  No provider needed.
- `injectable_keywords` = keywords in the job and master but not in tailored
  (the alignment engine can add them without inventing facts).
- `non_injectable_keywords` = keywords in the job but absent from both resumes
  (cannot be added truthfully).
- Do not claim the user possesses non-injectable skills.
