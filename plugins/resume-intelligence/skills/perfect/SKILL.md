---
name: perfect
description: >
  Final job-aware fit for a tailored resume: run the deterministic budget-fit
  capability, present ranked trim/compression candidates, drive decisions
  through the existing edit-session UX or use --auto-fit, and write the final
  resume only behind claim, ledger, and export page gates. No fabrication.
---

# perfect — final job-aware fit

Final step after tailoring and truth validation. This skill drives the
deterministic `fit` capability, which checks the tailored resume against the
shape policy's informational budgets, ranks trim/compression candidates against
the active job, and writes the final resume only when the edit-session gate
commits.

## Prerequisites

Run the shared **Prerequisites gate** — [`../_shared/prerequisites.md`](../_shared/prerequisites.md).

- **Required inputs:** an initialized `resume-kit/` project, a tailored
  `ResumeDocument` JSON for the job (normally the current active/resolved resume
  after `update-keywords` / `update-terminology`), and an active
  `JobDescription` JSON.
- **If no tailored resume exists:** STOP and run the tailoring skills first
  (`check-keywords`, `check-gaps`, then `update-keywords` /
  `update-terminology` as needed).
- **If no active job exists:** STOP and run **parse-job** first.
- **If the resume JSON is missing:** STOP and run **parse-resume** first, then
  baseline and tailor before fitting.

## What it does

1. **Budget check.** Run `resume-tool fit --root . --job <job>` to evaluate the
   resolved resume against the active job and current shape policy budgets.
2. **Present ranked work.** Show `violations`, ranked trim `candidates`, and
   `compressions`. Explain which items are deferred because they need judgment
   or failed a claim-preservation check.
3. **Drive decisions.** For the interactive path, use the existing
   edit-session decision UX to choose keep/drop/compress for the proposed
   changes. For the automated path, run `resume-tool fit --root . --auto-fit`.
4. **Report final state.** Show `final_path`, whether it `committed`, `applied`,
   `deferred`, and whether `ledger_ok` passed.

## How to invoke

**CLI**

```
resume-tool fit --root . [--job <jobs/job.json>] [--output {json,text,md}]
resume-tool fit --root . [--job <jobs/job.json>] --auto-fit [--output {json,text,md}]
```

`--job` is optional when `resume-kit/config.json` already has `active_job`.
`--auto-fit` uses ranked candidates to commit through the same edit-session
gate. Without `--auto-fit`, present the ranked candidates and drive the user's
decisions through the edit-session UX before committing.

**MCP tool:** `resume_build_perfect` (fields: `root`, `job`, `decisions`,
`auto_fit`).

## Truth and gates

- Never fabricate content to make the resume fit.
- Removals must be either explicit user decisions or ranked-budget-accounted
  automated drops.
- Compressions must pass the claim gate; failed or ambiguous compressions stay
  deferred.
- The content ledger is a HARD GATE for final fit accounting. If `ledger_ok` is
  false, surface the failure and do not treat the resume as final.
- Export remains the page-count HARD GATE: after fitting, run **export-resume**;
  export enforces `max_pages` and must pass before submission.
