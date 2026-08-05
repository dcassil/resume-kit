---
name: build-candidate-evidence
description: >
  Deterministically build a list of CandidateEvidence records from a resume,
  optionally seeded with pre-approved claims.  No LLM required.
---

> **Inputs must be canonical JSON.** This capability consumes a resume as a `ResumeDocument` JSON (build it from a PDF/DOCX/MD/text file with the **resume-to-json** skill) and, where a job is involved, a `JobDescription` JSON (build it with **job-to-json** so skills-coverage scoring works). Run those conversions in **subagents**, then pass the saved JSON paths here — they live under `resume-kit/resumes/` and `resume-kit/jobs/`.

## Prerequisites

Run the shared **Prerequisites gate** first — see
[`_shared/prerequisites.md`](../_shared/prerequisites.md).

- **Required input:** a resume/master `ResumeDocument` JSON (`config.json`
  `active_resume` or an explicit path).
- **If missing:** STOP and run **resume-to-json** to produce the `ResumeDocument`
  JSON before calling this skill.

## Purpose

Produce structured `CandidateEvidence` records that ground subsequent
`inject-keywords` / `update-terminology` and `validate-resume-truth` calls.  Evidence records capture
what the candidate can truthfully claim, preventing the alignment engine from
fabricating experience.

## When to use

- Before running `inject-keywords` or `update-terminology` with evidence constraints.
- Before running `validate-resume-truth` to produce an evidence baseline.
- When the user wants to review and approve their own claims before alignment.

## Inputs

| Field | Type | Notes |
|---|---|---|
| `resume` | `ResumeDocument` | Source resume from which evidence is derived |
| `approved_claims` | `list[CandidateEvidence] \| list[str] \| null` | Optional pre-approved claims to include (bypasses engine derivation for those items) |

**Options** (`CapabilityOptions`)

| Option | Default | Effect |
|---|---|---|
| `strict` | false | Escalate advisory warnings to failures |

`no_llm` has no effect — this capability is always deterministic.

## How to invoke

**CLI**

```
resume-tool build-evidence --resume <resume.json> \
    [--approved-claims <claims.json>] \
    [--output {json,text,md}] [--strict]
```

**MCP tool**: `candidate_evidence_build`

Input fields: `resume`, `approved_claims` (optional), `strict`.

## Output (`InterfaceResponse`)

| Field | Type | Notes |
|---|---|---|
| `data` | `list[CandidateEvidence]` | Evidence records derived from the resume |
| `warnings` | list | Advisory issues |
| `errors` | list | Failures |
| `requiresHumanInput` | bool | Always false |
| `questions` | list | Always empty |
| `provenance` | object | Source attribution |

## Notes

- Fully deterministic.  No provider needed.
- The returned evidence list is the authoritative input for truth validation
  and alignment.  Do not modify evidence records in agent code.
- If the user needs to approve claims before alignment, surface the returned
  list and collect approval before passing to `inject-keywords` / `update-terminology` as `evidence`.
