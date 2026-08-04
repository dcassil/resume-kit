---
name: compare-resume-versions
description: >
  Deterministically compare two resume versions (base vs candidate) against
  a job description and return a structured diff of their relative strengths.
  No LLM required.
---

## Purpose

Produce a `ResumeComparisonResult` that shows how two resume versions differ
in their job fit — useful for deciding whether a revised resume is an
improvement.

## When to use

- After editing a resume, to verify the new version scores better than the
  original.
- When a user wants side-by-side analysis of two variants before choosing
  which to submit.

## Inputs

| Field | Type | Notes |
|---|---|---|
| `base` | `ResumeDocument` | The reference (original) resume |
| `candidate` | `ResumeDocument` | The version being compared |
| `job` | `JobDescription` | The target job |
| `base_label` | str | Human label for `base` (default: `"base"`) |
| `candidate_label` | str | Human label for `candidate` (default: `"candidate"`) |

**Options** (`CapabilityOptions`)

| Option | Default | Effect |
|---|---|---|
| `strict` | false | Escalate advisory warnings to failures |

`no_llm` has no effect — this capability is always deterministic.

## How to invoke

**CLI**

```
resume-tool compare --base <base.json> --candidate <candidate.json> \
    --job <job.json> \
    [--base-label "original"] [--candidate-label "revised"] \
    [--output {json,text,md}] [--strict]
```

**MCP tool**: `resume_compare_versions`

Input fields: `base`, `candidate`, `job`, `base_label`, `candidate_label`,
`strict`.

## Output (`InterfaceResponse`)

| Field | Type | Notes |
|---|---|---|
| `data` | `ResumeComparisonResult` | Per-version scores and relative delta |
| `warnings` | list | Advisory issues |
| `errors` | list | Failures |
| `requiresHumanInput` | bool | Always false |
| `questions` | list | Always empty |
| `provenance` | object | Source attribution |

## Notes

- Fully deterministic.  No provider needed.
- Both resumes and the job must be already-extracted schema objects.
- Use `base_label` / `candidate_label` to produce human-readable output.
