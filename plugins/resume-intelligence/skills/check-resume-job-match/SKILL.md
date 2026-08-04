---
name: check-resume-job-match
description: >
  Compute a deterministic job match report showing how well a resume aligns
  with a job description across skills, experience, and keywords.
  No LLM required.
---

> **Inputs must be canonical JSON.** This capability consumes a resume as a `ResumeDocument` JSON (build it from a PDF/DOCX/MD/text file with the **resume-to-json** skill) and, where a job is involved, a `JobDescription` JSON (build it with **job-to-json** so skills-coverage scoring works). Run those conversions in **subagents**, then pass the saved JSON paths here — they live under `resume-kit/resumes/` and `resume-kit/jobs/`.

## Purpose

Produce a `JobMatchReport` that scores a resume against a job description and
identifies matched and missing requirements.  Used to decide whether a resume
needs alignment before applying.

## When to use

- To evaluate a resume against a specific job before submitting.
- To surface missing skills or experience gaps without running alignment.

## Inputs

| Field | Type | Notes |
|---|---|---|
| `resume` | `ResumeDocument` | Output of `extract-resume` |
| `job` | `JobDescription` | Output of `extract-job-description` |

**Options** (`CapabilityOptions`)

| Option | Default | Effect |
|---|---|---|
| `strict` | false | Escalate advisory warnings to failures |

`no_llm` has no effect — this capability is always deterministic.

## How to invoke

**CLI**

```
resume-tool match --resume <resume.json> --job <job.json> \
    [--output {json,text,md}] [--strict]
```

**MCP tool**: `resume_check_job_match`

Input fields: `resume`, `job`, `strict`.

## Output (`InterfaceResponse`)

| Field | Type | Notes |
|---|---|---|
| `data` | `JobMatchReport` | Match score, matched requirements, missing requirements |
| `warnings` | list | Advisory issues |
| `errors` | list | Failures |
| `requiresHumanInput` | bool | Always false |
| `questions` | list | Always empty |
| `provenance` | object | Source attribution |

## Honor the project synonym index

Read `resume-kit/config.json`'s `alias_file` (default
`resume-kit/learning/synonyms.json`) and pass it to this capability so the
grown, user-confirmed synonym index is honored: add `--alias-file <path>` on the
CLI, or set the `alias_file` field on the `resume_check_job_match` MCP request.
The engine UNIONs the project file over the seed lexicon; scoring stays fully
deterministic (no LLM).

## After scoring: grow the synonym index (truth-gated)

After you surface the match report, for each missing requirement/keyword that the
resume plausibly satisfies under a DIFFERENT surface term, run the shared
**`manage-synonyms`** workflow: it applies the truthfulness gate (genuine
same-skill synonym only — NetSuite↔SuiteCommerce yes, React≈Vue never), asks the
user to confirm, and only then appends a justified `{canonical, alias, why}`
entry to the alias file so the next deterministic run matches it. Never append
silently; always report exactly what was added. See the `manage-synonyms` skill
for the full workflow and file format. Scoring itself remains deterministic and
provider-free.

## Notes

- Fully deterministic.  No provider needed.
- Both inputs must be already-extracted schema objects.
- Do not interpret or augment the returned match data.  Surface it as-is to
  the user or downstream workflow.
