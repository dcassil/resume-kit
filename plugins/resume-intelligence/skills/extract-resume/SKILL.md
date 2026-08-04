---
name: extract-resume
description: >
  Extract a structured ResumeDocument from raw resume file bytes.
  Supports an LLM-powered structured parse (default) and a deterministic
  text-extraction path (--no-llm / no_llm=true).
---

## Purpose

Convert a raw resume file (PDF, DOCX, plain text) into a canonical
`ResumeDocument` schema object.  This is the entry point for every workflow
that needs parsed resume data.

## When to use

- Before passing resume data to any other capability.
- When the agent has a file path or raw bytes but needs structured fields.

## Inputs

| Field | Type | Notes |
|---|---|---|
| `content` | bytes | Raw file bytes |
| `filename` | str | Used to infer file type (e.g. `resume.pdf`) |

**Options** (`CapabilityOptions`)

| Option | Default | Effect |
|---|---|---|
| `no_llm` | false | Use deterministic text-only extraction (no provider needed) |
| `strict` | false | Escalate advisory warnings to failures |
| `provider` | null | Required when `no_llm` is false |

## How to invoke

**CLI**

```
resume-tool extract <file_path> [--output {json,text,md}] [--no-llm] [--strict]
```

**MCP tool**: `resume_extract`

Input fields: `content` (base64-encoded bytes), `filename`, `no_llm`, `strict`.

## Output (`InterfaceResponse`)

| Field | Type | Notes |
|---|---|---|
| `data` | `ResumeDocument` | Structured resume on success |
| `warnings` | list | Advisory issues (e.g. low-confidence fields) |
| `errors` | list | Failures preventing extraction |
| `requiresHumanInput` | bool | Always false for this capability |
| `questions` | list | Always empty for this capability |
| `provenance` | object | Source attribution |

## Notes

- **No-LLM mode**: Always available.  `extract_resume_text_only` returns a
  `ResumeDocument` with text-only fields; structured fields may be sparse.
- **LLM path**: Requires a configured provider.  Without one, the response
  contains an `PROVIDER_NOT_CONFIGURED` error and `data` is null.
- Do not invent resume content.  Act only on what the engine returns in `data`.
