---
name: check-resume-job-match
description: >
  Compute a deterministic job match report showing how well a resume aligns
  with a job description across skills, experience, and keywords.
  No LLM required.
---

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

## Notes

- Fully deterministic.  No provider needed.
- Both inputs must be already-extracted schema objects.
- Do not interpret or augment the returned match data.  Surface it as-is to
  the user or downstream workflow.
