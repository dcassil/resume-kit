---
name: complete-resume-flow
description: >
  Composite resume-intelligence workflow for producing a tailored, fitted, and
  exported resume from one prepared resume plus one or more jobs. Use when the
  user wants the complete end-to-end path or needs to understand the repeated
  use pattern across the four composable flows.
---

# complete-resume-flow - four composable flows

Use this as the single source of truth for the end-to-end flow order. The
per-stage gates live in the four smaller flow skills; do not duplicate those
gates here.

## Flow Order

1. Run **prepare-base-resume** once for a source resume.
   - Produces the reusable `original -> base -> structure -> refine` lineage.
   - Seeds durable full-resume evidence so source content that is omitted from
     the no-custom prepared artifact remains available as proof input.
   - Leaves `refine` as the default downstream tailoring input.
2. For each job, run **ingest-job**.
   - Parses and activates one job.
   - Grows and registers the project alias file through the truth-gated
     terminology learning path.
3. For that active job, run **tailor-resume**.
   - Scores the prepared resume against the active job.
   - Routes truthful keyword and terminology changes through the code-owned
     edit-session gate.
   - Validates facts and re-scores for deltas.
4. For the tailored resume, run **finalize-resume**.
   - Runs the job-aware fit pass.
   - Exports the final artifact; export remains the rendered page hard gate.

## Repeated Use

Run Flow 1 once per resume. Then run Flows 2, 3, and 4 many times, once for
each job, without rebuilding the prepared resume unless the source resume itself
changes.

## Compatibility

`resume-workflow` is retained as a compatibility entry point for existing users.
It points here and to the four smaller flow skills. Keep this skill short so the
stage gates cannot diverge from the flow-specific skills.
