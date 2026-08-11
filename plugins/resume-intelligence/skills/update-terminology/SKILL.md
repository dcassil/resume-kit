---
name: update-terminology
description: >
  Section-by-section terminology update through the code-owned edit-session
  orchestrator. When deterministic scoring finds a JD keyword the resume already
  satisfies under a different surface form, this skill uses suggest-terminology
  to enumerate truthful wording swaps, converts accepted candidates into
  ChangeProposal records, then drives review-edits open/prompt/decide/commit and
  validate-facts. Direct hand-editing is unsupported unless followed by
  reconcile-session. Best run in a subagent.
---

# update-terminology - suggest -> edit session -> commit gate -> truth

## Purpose

`check-keywords` and `check-gaps` score a resume against a job
deterministically. When the resume already demonstrates a required skill under a
different surface form, the employer's exact wording can be mirrored without
inventing a new claim.

This skill's **create-change** step turns those wording swaps into targeted
`ChangeProposal` records, then hands them to the shared change-application
runbook — the same decide → commit-gate → validate → learn spine used by
**update-keywords**. It does not directly edit the resume or bypass review.

To add a keyword the resume was missing but the master proves, use
**update-keywords**. To surface a keyword absent from both this resume and the
master/evidence, report a gap; never rewrite it in.

## Prerequisites Gate

Run the shared prerequisites gate in
[`../_shared/prerequisites.md`](../_shared/prerequisites.md). Required inputs:

- A `ResumeDocument` JSON.
- A `JobDescription` JSON.
- The project `alias_file` from `resume-kit/config.json`, defaulting to
  `resume-kit/learning/synonyms.json` when present.

If the resume or job JSON is missing, stop and run **parse-resume** or
**parse-job** first.

**Evidence precondition (required).** Terminology swaps are truth-gated: the
accept path re-validates the swapped wording with `validate_resume_truth`
against the project's `CandidateEvidence`. With no evidence the gate cannot
substantiate any wording, so every swap is rejected (not applied) with the
reason "no candidate evidence — run extract-evidence first". Run
**extract-evidence** before this skill so the gate can substantiate the swaps;
a swap is only ever reported as applied when it passed the truth gate.

## Run Me In A Subagent

This is a self-contained improve task over potentially large resume/job data.
Hand the subagent the active resume path, job path, `resume-kit/config.json`,
resolved `alias_file`, and this skill. The subagent returns only the proposed
and committed changes, skipped suggestions, gate results, and score deltas.

## Surface This Skill Drives (create-change input)

- Terminology suggestions: CLI `resume-tool suggest-terminology`, MCP
  `resume_suggest_terminology`, facade capability `suggest-terminology`.

The edit-session, truth-validation, and re-score surfaces are owned by the shared
runbook (see below).

## Steps (create-change)

1. **Resolve and pass `alias_file`.** Use the same alias index that
   **check-keywords** uses.
2. **Analyze suggestions.** Run `suggest-terminology` with the resume, job, and
   alias file. It returns wording suggestions for skills the resume already
   satisfies under another term.
3. **Convert suggestions to `ChangeProposal` records.** For each truthful
   suggestion, build a minimal `replace` change at the suggested location with
   the full current text as `original`, the employer-worded text as `value`, and
   a reason naming the alias hit. Do not target identity, employer,
   title-of-record, or date fields.

## Apply the changes

Hand the `ChangeProposal` records to the shared change-application runbook and
follow it end to end:
[`../_shared/apply-changes.md`](../_shared/apply-changes.md). It owns mode
selection, the open/prompt/decide loop and reason codes, the `commit-session`
hard gate, `validate-facts`, the automatic learn tail (accepted terminology edits
grow `learn-terminology` aliases at commit), and the re-score.

## Truth Posture

Follow the shared truth posture in the runbook, plus:

- Only mirror wording for a skill the resume already demonstrates.
- Never turn an absent skill into a claimed skill.
- Route durable synonym questions through **learn-terminology**.

## Output

Return the runbook's normal output (committed `working_path`, session id,
decided changes, gate rejections, grown aliases, before/after match deltas) with
each applied terminology change carrying its `{path, old, new}`, and every
rejected/skipped suggestion with its reason code when supplied.
