---
name: finalize-resume
description: >
  Run the final job-aware fit and export over a tailored resume, enforce the
  rendered page hard gate, and do no preparation, job ingest, or tailoring.
  Best run in a subagent.
---

# finalize-resume — tailored resume → fitted export

Flow 4 of the composable resume workflow. Run this after **tailor-resume** has
already produced a tailored resume for the active job. This flow owns the final
fit pass through **perfect**, then the rendered artifact pass through
**export-resume**.

It does not prepare the master resume, ingest a job, learn terminology, or apply
tailoring updates. It only fits and exports the already-tailored resume.

## Prerequisites

Run the shared **Prerequisites gate** —
[`../_shared/prerequisites.md`](../_shared/prerequisites.md).

- **Required inputs:** a **tailored `ResumeDocument` JSON** and an
  **`active_job` `JobDescription` JSON**.
- **If no tailored resume exists:** STOP and run **tailor-resume** first.
- **If no active job exists:** STOP and run **ingest-job** first.
- **If the resume JSON is missing:** STOP and run **parse-resume**, then the
  preparation and tailoring flows before finalizing.

## The walkthrough

1. **`perfect`.** Run **perfect** with `resume-tool fit` against the tailored
   resume and active job. Use either the decision-driven path or explicit
   `--auto-fit`. For decision-driven trims, preserve the explicit
   decision/accounting behavior: removals must be accepted by the user or
   ranked-budget-accounted automated drops, compressions must pass the claim
   gate, and deferred items remain reported rather than invented or forced.
2. **`export-resume`.** Run **export-resume** after **perfect** writes the
   fitted resume. Export enforces the rendered `max_pages` HARD gate. Fit is
   not submission-ready until export passes: rendered output is authoritative;
   **perfect** may warn or fit to budgets, but it does not replace the export
   page gate.

## How to invoke

**CLI**

```
resume-tool fit --root . [--job <jobs/job.json>] [--output {json,text,md}]
resume-tool fit --root . [--job <jobs/job.json>] --auto-fit [--output {json,text,md}]
resume-tool export --format {pdf,docx} [--out PATH] [--resume <resume.json>]
```

`--job` is optional when `resume-kit/config.json` already has `active_job`.
Pass the fitted `final_path` from `resume-tool fit` to `resume-tool export`
when it is not already the active resume.

**MCP tools:** `resume_build_perfect`, then `resume_export`.

## Guardrails

- Does not mutate master lineage: `original`, `base`, `structure`, or `refine`.
- Does not run preparation, job ingest, terminology learning, keyword updates,
  terminology updates, or any other tailoring step.
- Does not fabricate content to satisfy budgets or page limits.
- Does not treat **perfect** output as final for submission until
  **export-resume** passes the rendered page hard gate.
