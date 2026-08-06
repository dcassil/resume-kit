---
name: select-resume
description: >
  Select the best-matching resume from a set of candidates for a given job
  description.  No LLM required.
---

> **Renamed:** `select-resume` was `select-best-resume` before v1.0.0 (see RIT-A-0005).

> **Inputs must be canonical JSON.** This capability consumes a resume as a `ResumeDocument` JSON (build it from a PDF/DOCX/MD/text file with the **parse-resume** skill) and, where a job is involved, a `JobDescription` JSON (build it with **parse-job** so skills-coverage scoring works). Run those conversions in **subagents**, then pass the saved JSON paths here — they live under `resume-kit/resumes/` and `resume-kit/jobs/`.

## Prerequisites

Run the shared **Prerequisites gate** first — see
[`_shared/prerequisites.md`](../_shared/prerequisites.md).

- **Required inputs:** a set of candidate `ResumeDocument` JSONs (two or more)
  **and** a `JobDescription` JSON (`config.json` `active_job` or an explicit path).
- **If missing:** STOP and name the upstream skill — any missing resume JSON → run
  **parse-resume**; missing job JSON → run **parse-job**.

## Purpose

Rank a collection of `ResumeDocument` objects against a `JobDescription` and
return the best match as a `ResumeSelectionResult`.  Useful when a candidate
maintains multiple resume variants.

## When to use

- When the user has two or more resume versions and needs to pick the right
  one to submit for a job.
- As a pre-step before deciding whether alignment is worth running.

## Inputs

| Field | Type | Notes |
|---|---|---|
| `resumes` | `list[ResumeDocument]` | At least one resume; order does not matter |
| `job` | `JobDescription` | The target job |
| `labels` | `list[str] \| null` | Optional human-readable names for each resume (parallel to `resumes`) |

**Options** (`CapabilityOptions`)

| Option | Default | Effect |
|---|---|---|
| `strict` | false | Escalate advisory warnings to failures |

`no_llm` has no effect — this capability is always deterministic.

## How to invoke

**CLI**

```
resume-tool select --resumes <r1.json> <r2.json> --job <job.json> \
    [--labels "version-a" "version-b"] \
    [--output {json,text,md}] [--strict]
```

**MCP tool**: `resume_select_best`

Input fields: `resumes` (list of serialized `ResumeDocument`), `job`,
`labels` (optional list of strings), `strict`.

## Output (`InterfaceResponse`)

| Field | Type | Notes |
|---|---|---|
| `data` | `ResumeSelectionResult` | Selected resume index, label, and scores for all candidates |
| `warnings` | list | Advisory issues |
| `errors` | list | Failures |
| `requiresHumanInput` | bool | Always false |
| `questions` | list | Always empty |
| `provenance` | object | Source attribution |

## Notes

- Fully deterministic.  No provider needed.
- Pass labels to make the result human-readable when presenting to the user.
- The engine selects by match score; do not override the engine's selection in
  agent logic.
