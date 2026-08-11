---
name: prepare-base-resume
description: >
  Prepare one resume without needing a job: produce an ATS-ready, no-custom
  canonical artifact for downstream tailoring, and seed durable full-resume
  learning from the source resume first so custom and unmapped content remain
  available as evidence. Best run in a subagent.
---

# prepare-base-resume - reusable Flow 1 baseline

Flow 1 prepares a single resume before any job-specific work. It turns a source
resume into the normal `original -> base -> structure -> refine` lineage, keeps
`refine` as the default downstream tailoring input, and seeds durable evidence
from the full source resume before the prepared no-custom projection removes
custom or unmapped sections from the canonical artifact.

## Prerequisites

Run the shared **Prerequisites gate** -
[`../_shared/prerequisites.md`](../_shared/prerequisites.md).

- **Required input:** one source resume file or one already-parsed
  `ResumeDocument` JSON.
- **Does NOT need a job.** This flow is entirely job-independent.
- **Project state:** `resume-kit/config.json` may already point at other resumes,
  jobs, aliases, or learning files. This flow must update only the active resume
  lineage and evidence pointers needed for the resume being prepared.

## The walkthrough

1. **Parse the resume.** Run **parse-resume** if the source is a PDF, DOCX,
   Markdown, or text file. Save the faithful `<name>-original.json` and set it
   active with `resume-tool set-active --resume resumes/<name>-original.json`
   plus `--resume-source` when a source file exists.
2. **Seed full-resume learning before projection.** Call
   `seed-full-resume-evidence` while `active_resume` still points at the full
   source resume. This captures all source content, including custom and
   unmapped sections, into durable learning evidence before the no-custom
   prepared artifact omits those sections.
3. **Build `base`.** Run **update-structure** (`build-base`) to apply the
   resume-only ATS structural fixes behind the claim-preservation gate. This
   writes `resume-kit/resumes/<name>-base.json`.
4. **Build canonical no-custom `structure`.** Run **update-shape**
   (`build-structure`) as the no-custom Flow 1 projection. It must account for
   every source token through the content ledger, preserve ambiguous/custom
   content in learning evidence rather than a canonical custom section, and
   write `resume-kit/resumes/<name>-structure.json` only when its hard gates
   pass.
5. **Score best practices.** Run **check-best-practices** on the `structure`
   artifact. Split findings into `auto_suggestible` and `needs_user_input`.
6. **Build `refine`.** Run **update-refine** (`build-refine`) with truthful
   answers for any `needs_user_input` findings the user can actually support.
   Unanswered findings remain deferred; they are never fabricated. This writes
   `resume-kit/resumes/<name>-refine.json`.
7. **Optionally inspect ATS view.** Run **check-ats-view** on `refine` when the
   user wants the read-only parser view before tailoring starts.

## How to invoke

**CLI seed step**

```bash
resume-tool seed-full-resume-evidence --root . [--output {json,text,md}]
```

Run after `parse-resume` / `set-active`, before `build-base` and
`build-structure`.

**MCP seed step:** `resume_seed_full_resume_evidence` with optional
`{"root": "."}`.

The rest of the flow uses the existing surfaces: `resume-tool build-base`,
`resume-tool build-structure`, `resume-tool analyze-best-practices`, and
`resume-tool build-refine`; MCP tools `resume_build_base`,
`resume_build_structure`, `resume_analyze_best_practices`, and
`resume_build_refine`.

## Truth posture

- No-custom output must not silently drop ambiguous content. Flow 1 retains the
  full source resume in durable learning evidence first, then projects the
  prepared artifact.
- Learning evidence is proof input only. It does not bypass truth,
  faithfulness, claim-preservation, content-ledger, or edit-session gates.
- Every edit still passes the existing gates. If a gate refuses, stop and report
  the refusal; do not patch JSON by hand.
- Never fabricate facts for best-practices answers, metrics, section mappings,
  or evidence records.

## Multiple resumes

This flow can be run for multiple resumes in the same project. Each run may
change the active resume lineage for the resume being prepared and may merge new
records into `learning/candidate-evidence.json`, but it must not clobber
unrelated learning files, alias pointers, job pointers, or previous resume
artifacts. After a run completes, `refine` remains the default downstream
tailoring input for that active resume.
