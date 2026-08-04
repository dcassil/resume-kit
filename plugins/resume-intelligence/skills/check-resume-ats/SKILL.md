---
name: check-resume-ats
description: >
  Compute a deterministic ATS (applicant tracking system) compatibility score
  for a resume against a job description.  No LLM required.
---

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

## Notes

- Fully deterministic.  Safe to run with `--no-llm` or with no provider configured.
- Both `resume` and `job` must be already-extracted schema objects.  Run
  `extract-resume` and `extract-job-description` first.
