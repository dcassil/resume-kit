---
name: extract-job-description
description: >
  Extract a structured JobDescription from raw job posting text.
  Supports an LLM-powered keyword extraction path (default) and a
  deterministic text-only path (--no-llm / no_llm=true).
---

## Purpose

Convert a raw job posting string into a canonical `JobDescription` schema
object with structured fields (title, required skills, keywords, etc.).

## When to use

- Before passing job data to any matching, ATS, gap, or alignment capability.
- When the agent has raw text copied from a job board or description field.

## Inputs

| Field | Type | Notes |
|---|---|---|
| `raw_text` | str | Full text of the job posting |

**Options** (`CapabilityOptions`)

| Option | Default | Effect |
|---|---|---|
| `no_llm` | false | Use deterministic text-only parse (no provider needed) |
| `strict` | false | Escalate advisory warnings to failures |
| `provider` | null | Required when `no_llm` is false |

## How to invoke

**CLI**

```
resume-tool extract-job <text_file_or_stdin> [--output {json,text,md}] [--no-llm] [--strict]
```

**MCP tool**: `job_description_extract`

Input fields: `raw_text`, `no_llm`, `strict`.

## Output (`InterfaceResponse`)

| Field | Type | Notes |
|---|---|---|
| `data` | `JobDescription` | Structured job description on success |
| `warnings` | list | Advisory issues |
| `errors` | list | Failures preventing parsing |
| `requiresHumanInput` | bool | Always false for this capability |
| `questions` | list | Always empty for this capability |
| `provenance` | object | Source attribution |

## Notes

- **No-LLM mode**: Always available.  `parse_job_description_text_only`
  produces a `JobDescription` from heuristic parsing; structured keyword
  fields may be less complete than the LLM path.
- **LLM path**: Requires a configured provider.  Without one, the response
  contains a `PROVIDER_NOT_CONFIGURED` error and `data` is null.
- Do not add keywords or requirements not present in the source text.
