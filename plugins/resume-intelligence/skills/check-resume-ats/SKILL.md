---
name: check-resume-ats
description: >
  Compute a deterministic ATS (applicant tracking system) compatibility score
  for a resume against a job description.  No LLM required.
---

> **Inputs must be canonical JSON.** This capability consumes a resume as a `ResumeDocument` JSON (build it from a PDF/DOCX/MD/text file with the **resume-to-json** skill) and, where a job is involved, a `JobDescription` JSON (build it with **job-to-json** so skills-coverage scoring works). Run those conversions in **subagents**, then pass the saved JSON paths here — they live under `resume-kit/resumes/` and `resume-kit/jobs/`.

## Purpose

Score how well a resume will pass automated ATS filters for a specific job.
Returns an `ATSScore` with match percentage, injectable keywords, and
non-injectable keywords.

## When to use

- To estimate ATS pass-through before applying or aligning.
- As a fast, deterministic pre-filter when no LLM provider is available.

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
resume-tool check-ats --resume <resume.json> --job <job.json> \
    [--output {json,text,md}] [--strict]
```

**MCP tool**: `resume_check_ats`

Input fields: `resume` (serialized `ResumeDocument`), `job` (serialized
`JobDescription`), `strict`.

## Output (`InterfaceResponse`)

| Field | Type | Notes |
|---|---|---|
| `data` | `ATSScore` | Score object with `match_percentage`, `injectable_keywords`, `non_injectable_keywords` |
| `warnings` | list | Advisory issues |
| `errors` | list | Failures |
| `requiresHumanInput` | bool | Always false |
| `questions` | list | Always empty |
| `provenance` | object | Source attribution |

## Honor the project synonym index

Read `resume-kit/config.json`'s `alias_file` (default
`resume-kit/learning/synonyms.json`) and pass it to this capability so the
grown, user-confirmed synonym index is honored: add `--alias-file <path>` on the
CLI, or set the `alias_file` field on the `resume_check_ats` MCP request. The
engine UNIONs the project file over the seed lexicon; scoring stays fully
deterministic (no LLM).

## After scoring: grow the synonym index (truth-gated)

After you report the score, for each job keyword that came back **missing** but
which the resume plausibly satisfies under a DIFFERENT surface term, run the
shared **`manage-synonyms`** workflow: it applies the truthfulness gate
(genuine same-skill synonym only — NetSuite↔SuiteCommerce yes, React≈Vue never),
asks the user to confirm, and only then appends a justified `{canonical, alias,
why}` entry to the alias file so the next deterministic run matches it. Never
append silently; always report exactly what was added. See the `manage-synonyms`
skill for the full workflow and file format. This is data-authoring by the agent
— scoring itself remains deterministic and provider-free.

## Notes

- Fully deterministic.  Safe to run with `--no-llm` or with no provider configured.
- Both `resume` and `job` must be already-extracted schema objects.  Run
  `extract-resume` and `extract-job-description` first.
