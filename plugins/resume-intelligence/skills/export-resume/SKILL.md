---
name: export-resume
description: >
  Render a ResumeDocument to a downloadable PDF or DOCX artifact.
  Fully deterministic and requires no LLM provider — always works with no_llm.
  Uses ReportLab (PDF) and python-docx (DOCX) inside packages/export; no
  Chromium or upstream frontend involved.
---

> **Inputs must be canonical JSON.** This capability consumes a resume as a `ResumeDocument` JSON (build it from a PDF/DOCX/MD/text file with the **parse-resume** skill) and, where a job is involved, a `JobDescription` JSON (build it with **parse-job** so skills-coverage scoring works). Run those conversions in **subagents**, then pass the saved JSON paths here — they live under `resume-kit/resumes/` and `resume-kit/jobs/`.

## Prerequisites

Run the shared **Prerequisites gate** first — see
[`_shared/prerequisites.md`](../_shared/prerequisites.md).

- **Required input:** a `ResumeDocument` JSON (`config.json` `active_resume`, a
  `resume-kit/working/<session>/resume.json`, or an explicit path).
- **If missing:** STOP and run **parse-resume** to produce the `ResumeDocument`
  JSON before exporting.

## Purpose

Render a `ResumeDocument` to bytes and persist them through an `ArtifactStore`.
The response `data` field carries an `ArtifactRef` (also present in `artifacts`)
that the caller uses to retrieve the rendered bytes — raw bytes are never
embedded directly in the envelope.  The artifact id is deterministic: callers
may supply an explicit `artifact_id`; otherwise it is derived from a SHA-256
hash of the format plus the rendered content (no UUIDs, timestamps, or random
values).

## When to use

- When the user wants a finished, downloadable resume file (PDF or DOCX).
- After `update-keywords`, `update-terminology`, or any editing step, to produce the final artifact.
- When a downstream system requires a binary file rather than a JSON document.

## Inputs

| Field | Type | Notes |
|---|---|---|
| `resume` | `ResumeDocument` | The resume to render |
| `format` | `"pdf" \| "docx"` | Output format |
| `options` | `ExportOptions \| null` | Optional render options (see below) |
| `artifact_id` | `str \| null` | Optional explicit artifact id; omit for deterministic hash |

**`ExportOptions`** (all fields optional; defaults shown)

| Option | Default | Effect |
|---|---|---|
| `font_family` | `"Helvetica"` | Base font family name |
| `font_size_pt` | `11` | Body font size in points |
| `margin_mm` | `20.0` | Page margin in millimetres (all sides) |
| `include_hyperlinks` | `true` | Render URLs as clickable hyperlinks when supported |
| `page_size` | `"letter"` | Page size identifier: `"letter"` or `"a4"` |

**Options** (`CapabilityOptions`)

| Option | Default | Effect |
|---|---|---|
| `no_llm` | false | Has no effect — this capability is always deterministic |
| `strict` | false | Escalate advisory warnings to failures |
| `artifact_store` | in-memory | Custom `ArtifactStore` for byte persistence (MCP/API inject one automatically) |

## How to invoke

**CLI**

```
resume-tool export --format {pdf,docx} [--out PATH] [--resume <resume.json>]
```

`--out PATH` writes the rendered bytes to disk.  When omitted the bytes are
written to a default path derived from the artifact id.

**MCP tool**: `resume_export`

Input fields: `resume`, `format`, `options` (optional), `artifact_id` (optional).

**API**: `POST /export`

Body: `ExportBody` — `resume`, `format`, optional `options`.  The response
envelope carries the `ArtifactRef`; bytes are returned as base64 in the
transport layer.

**Facade bridge**: `export_resume` (registered as `"export-resume"` in the
capability registry).

## Output (`InterfaceResponse`)

| Field | Type | Notes |
|---|---|---|
| `data` | `ArtifactRef` | Retrieval handle for the rendered bytes |
| `artifacts` | `list[ArtifactRef]` | Always contains the same single `ArtifactRef` as `data` |
| `warnings` | list | Advisory issues |
| `errors` | list | Failures (e.g. unsupported format, render error) |
| `requiresHumanInput` | bool | Always false |
| `questions` | list | Always empty |
| `provenance` | object | Source attribution |

**`ArtifactRef` fields**

| Field | Notes |
|---|---|
| `artifact_id` | Deterministic id (caller-supplied or SHA-256 hash) |
| `content_type` | `application/pdf` or `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| `metadata` | `{"format": "pdf"}` or `{"format": "docx"}` |

## Notes

- **Fully deterministic.** No provider needed.  `no_llm` is ignored because
  the capability never calls an LLM.
- **No Chromium, no frontend.** Rendering uses ReportLab (PDF) and
  python-docx (DOCX) exclusively inside `packages/export`.
- **Bytes retrieval**: CLI writes to `--out PATH`.  MCP and API transports
  return the bytes as base64 inside the `ArtifactRef` payload.  Do not attempt
  to read raw bytes from `data` directly in agent code; use the `ArtifactRef`
  retrieval API instead.
- **Artifact id stability**: Given the same resume content and format, the
  derived artifact id is identical across invocations.  Pass an explicit
  `artifact_id` when you need a human-readable or externally meaningful id.
- **`artifact_store`**: Callers may inject a custom `ArtifactStore` via
  `CapabilityOptions` for durable storage (e.g. S3-backed).  When none is
  provided, an in-memory store is used for the lifetime of the call.
