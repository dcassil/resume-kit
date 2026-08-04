---
name: align-resume
description: >
  Align a resume to a job description using controlled LLM-powered rewriting.
  Requires a configured provider.  Supports human-in-loop mode where the
  engine pauses and surfaces questions before advancing.
---

> **Inputs must be canonical JSON.** This capability consumes a resume as a `ResumeDocument` JSON (build it from a PDF/DOCX/MD/text file with the **resume-to-json** skill) and, where a job is involved, a `JobDescription` JSON (build it with **job-to-json** so skills-coverage scoring works). Run those conversions in **subagents**, then pass the saved JSON paths here — they live under `resume-kit/resumes/` and `resume-kit/jobs/`.

## Purpose

Produce an `AlignmentResult` containing the original resume and an
`aligned_resume` tailored to the job.  The engine operates under a policy
that prevents fabricating experience or bypassing candidate evidence.

## When to use

- After `identify-resume-gaps` confirms injectable keywords exist.
- When the user explicitly requests resume tailoring for a specific job.
- Do not run alignment to add skills the candidate does not possess; use
  evidence to constrain what the engine may claim.

## Inputs

| Field | Type | Notes |
|---|---|---|
| `resume` | `ResumeDocument` | The resume to align |
| `job` | `JobDescription` | The target job |
| `evidence` | `list[CandidateEvidence] \| null` | Optional candidate evidence records to constrain the engine |

**Options** (`CapabilityOptions`)

| Option | Default | Effect |
|---|---|---|
| `no_llm` | false | Returns original resume unchanged (no-op deterministic path) |
| `strict` | false | Escalate advisory warnings to failures |
| `human_in_loop` | false | Engine pauses and surfaces `requiresHumanInput=true` with questions before generating |
| `provider` | null | **Required** when `no_llm` is false |

## How to invoke

**CLI**

```
resume-tool align --resume <resume.json> --job <job.json> \
    [--evidence <evidence.json>] \
    [--human-in-loop | --non-interactive] \
    [--output {json,text,md}] [--strict]
```

**MCP tool**: `resume_align`

Input fields: `resume`, `job`, `evidence` (optional), `no_llm`, `strict`,
`human_in_loop`.

## Output (`InterfaceResponse`)

| Field | Type | Notes |
|---|---|---|
| `data` | `AlignmentResult` | `original_resume`, `aligned_resume`, `job` — or null if paused |
| `warnings` | list | Advisory issues from the engine |
| `errors` | list | Failures including `PROVIDER_NOT_CONFIGURED` |
| `requiresHumanInput` | bool | True when `human_in_loop=true` and the engine needs a decision |
| `questions` | list | Questions the human must answer before alignment proceeds |
| `provenance` | object | Source attribution |

## Notes

- **No-LLM mode**: `--no-llm` returns `aligned_resume == original_resume`.
  Use it to test the workflow without a provider.
- **Provider required**: Without a configured provider (and `no_llm=false`),
  the response contains a `PROVIDER_NOT_CONFIGURED` error and `data` is null.
- **Human-in-loop**: When `requiresHumanInput` is true, present `questions`
  to the user, collect answers, then re-invoke with the answers supplied.
  Do not advance alignment without the required human decision.
- **Evidence constraint**: Pass `CandidateEvidence` records (from
  `build-candidate-evidence`) to restrict what the engine may claim.  Without
  evidence the engine uses only resume content as its grounding.
- Do not modify the `aligned_resume` in agent code.  Surface the engine output
  as-is.
- **Terminology mirrors:** if the resume already satisfies a JD keyword under a
  different surface form (an alias hit — e.g. "k8s" vs "Kubernetes"), use the
  **`align-terminology`** skill to mirror the employer's exact wording (truthful,
  human-in-loop, no LLM) rather than a full alignment run.
