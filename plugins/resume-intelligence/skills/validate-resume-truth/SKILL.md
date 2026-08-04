---
name: validate-resume-truth
description: >
  Deterministically validate resume claims against candidate evidence records.
  Returns a TruthReport flagging unsupported or contradicted claims.
  No LLM required.
---

## Purpose

Cross-reference a `ResumeDocument` against a list of `CandidateEvidence`
records and produce a `TruthReport` that identifies which resume claims are
supported, unsupported, or contradicted by evidence.

## When to use

- Before running `align-resume` to ensure only truthful content is present.
- After alignment to verify the aligned resume does not contain fabricated
  claims.
- When the user wants an evidence-backed audit of a resume.

## Inputs

| Field | Type | Notes |
|---|---|---|
| `resume` | `ResumeDocument` | The resume to validate |
| `evidence` | `list[CandidateEvidence]` | Evidence records (may be empty; empty list produces a report with all claims unsupported) |

**Options** (`CapabilityOptions`)

| Option | Default | Effect |
|---|---|---|
| `strict` | false | Escalate advisory warnings to failures |

`no_llm` has no effect — this capability is always deterministic.

## How to invoke

**CLI**

```
resume-tool validate-truth --resume <resume.json> \
    [--evidence <evidence.json>] \
    [--output {json,text,md}] [--strict]
```

**MCP tool**: `resume_validate_truth`

Input fields: `resume`, `evidence` (optional list), `strict`.

## Output (`InterfaceResponse`)

| Field | Type | Notes |
|---|---|---|
| `data` | `TruthReport` | Per-claim verdicts: supported / unsupported / contradicted |
| `warnings` | list | Advisory issues |
| `errors` | list | Failures |
| `requiresHumanInput` | bool | Always false |
| `questions` | list | Always empty |
| `provenance` | object | Source attribution |

## Notes

- Fully deterministic.  No provider needed.
- An empty `evidence` list is valid; all claims will be marked unsupported.
- Do not suppress or ignore `contradicted` claims in agent output.  Present
  the full report to the user.
- Use `build-candidate-evidence` to produce the evidence list from a resume
  before running validation.
