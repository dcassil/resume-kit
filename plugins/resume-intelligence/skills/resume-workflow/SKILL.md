---
name: resume-workflow
description: >
  Compatibility entry-point guide for the resume-intelligence end-to-end
  workflow. Use when a user asks for the older resume-workflow guide; it points
  to complete-resume-flow and the four composable flow skills rather than
  duplicating their stage gates.
---

# resume-workflow - compatibility entry point

Use **complete-resume-flow** for the canonical end-to-end order:

1. **prepare-base-resume**
2. **ingest-job**
3. **tailor-resume**
4. **finalize-resume**

The four smaller flow skills are the source of truth for per-stage gates and
walkthrough details. This skill is retained so existing prompts that name
`resume-workflow` still route correctly, but it must stay a thin pointer rather
than a second copy of the workflow.

## Repeated Use

Run **prepare-base-resume** once per resume. Then run **ingest-job**,
**tailor-resume**, and **finalize-resume** repeatedly for each job without
rerunning resume preparation unless the source resume changes.

## Optional Supporting Skills

Use these from within the four flows when their respective flow skill calls for
them:

- **check-ats-view**: optional read-only parser view after preparation.
- **review-resume**: optional advice-only review after a tailored resume exists.
- **interview-missing-job-description**: optional truth-gated interview when the
  second tailoring score is still low or required coverage remains missing.
- **compare-versions** and **select-resume**: optional maintenance utilities for
  multi-resume projects.
