---
name: check-best-practices
description: >
  Check a resume against generic, job-INDEPENDENT best practices — buzzwords,
  weak/duty openers, missing quantification, bullet quality — and report each
  finding classified auto_suggestible vs needs_user_input. Read-only: it scores
  and reports, it never edits the resume. Drives the deterministic
  analyze-best-practices capability. No per-item LLM. Best run in a subagent.
---

# check-best-practices — generic best-practices score (read-only)

Baselining step 2 of `original → base → standard` (RIT-I-0016). Runs the generic,
job-independent best-practices analyzer on the `base` resume and reports the
findings. It is the read-only counterpart to **update-best-practices**, which
acts on these findings — this skill **never edits the resume**.

## Prerequisites

Run the shared **Prerequisites gate** — [`../_shared/prerequisites.md`](../_shared/prerequisites.md).

- **Required input:** a **`ResumeDocument` JSON** — normally the `base` version
  (run **update-structure** first); the active resume otherwise.
- **Does NOT need a job.** The best-practices score is job-independent.
- **If no `base` exists yet:** run **update-structure** first so the score
  reflects the structurally-cleaned resume.

## What it does

Run `analyze-best-practices` on the resume and present the `BestPracticesReport`.
Each finding carries a severity (per the RIT-A-0003 taxonomy) and a **resolution
classification**:

- **`auto_suggestible`** — a concrete, truthful rewrite is available now (carried
  as `suggested_change`).
- **`needs_user_input`** — the fix requires a fact the system does not have (e.g.
  a real metric to quantify a bullet); carries an `elicitation_prompt`.

Group findings by resolution kind so the caller can see, at a glance, what
**update-best-practices** can fix automatically vs what will require answering a
question.

## How to invoke

**CLI**

```
resume-tool analyze-best-practices --resume <base.json> [--output {json,text,md}]
```

**MCP tool:** `resume_analyze_best_practices`. Input field: `resume`. There is no
`job` and no `alias_file` — the score is job-independent and deterministic across
every surface.

## Output (`BestPracticesReport`)

Present the findings as-is: each finding's rule, severity, location, resolution
kind, and either its `suggested_change` (auto_suggestible) or `elicitation_prompt`
(needs_user_input). Do **not** apply any change — that is
**update-best-practices**' job. Do not blend these into a composite ATS score;
this is a standalone best-practices signal.

## Notes

- Fully deterministic; no provider needed. Introduces no per-item LLM calls, so
  output is identical across CLI/MCP/API.
- Single responsibility: score + classify only. To act on the findings and write
  the `standard` version, run **update-best-practices**.
