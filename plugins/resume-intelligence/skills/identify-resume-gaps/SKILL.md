---
name: identify-resume-gaps
description: >
  Deterministically analyse keyword gaps between a tailored resume, a master
  resume, and a job description.  Returns injectable and non-injectable
  missing keywords.  No LLM required.
---

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

## Notes

- Fully deterministic.  No provider needed.
- `injectable_keywords` = keywords in the job and master but not in tailored
  (the alignment engine can add them without inventing facts).
- `non_injectable_keywords` = keywords in the job but absent from both resumes
  (cannot be added truthfully).
- Do not claim the user possesses non-injectable skills.
