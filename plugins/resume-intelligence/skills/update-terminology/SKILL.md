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

This skill handles those wording swaps. It does not directly edit the resume and
does not call an apply command to bypass review. It creates targeted
`ChangeProposal` records and sends them through the same edit-session loop used
by **update-keywords**.

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

## Run Me In A Subagent

This is a self-contained improve task over potentially large resume/job data.
Hand the subagent the active resume path, job path, `resume-kit/config.json`,
resolved `alias_file`, and this skill. The subagent returns only the proposed
and committed changes, skipped suggestions, gate results, and score deltas.

## Working Directory

```
resume-kit/
├── config.json
├── resumes/<name>-original.json
├── jobs/<name>-original.json
├── working/edit-session.json
├── working/<name>.tailored.json
└── learning/
    └── synonyms.json
```

The edit-session commit writes the tailored resume to its reported
`working_path`. Do not create, overwrite, or bulk-edit that file yourself. If the
user intentionally edits it out of band, run `resume-tool review-edits reconcile`
/ `edit_session_reconcile` / `reconcile-session` before continuing.

## Surfaces This Skill Drives

- Terminology suggestions: CLI `resume-tool suggest-terminology`, MCP
  `resume_suggest_terminology`, facade capability `suggest-terminology`.
- Edit session:
  - CLI `resume-tool review-edits open --mode <interactive|review_at_end|auto>`
  - CLI `resume-tool review-edits prompt`
  - CLI `resume-tool review-edits decide --path <path> --action <approve|reject|edit|skip>`
  - CLI `resume-tool review-edits commit`
  - CLI `resume-tool review-edits status`
  - CLI `resume-tool review-edits reconcile`
  - MCP `edit_session_open`, `edit_session_prompt`, `edit_session_decide`,
    `edit_session_commit`, `edit_session_status`, `edit_session_reconcile`
  - Facade capabilities `open-edit-session`, `session-prompt`, `decide-change`,
    `commit-session`, `session-status`, `reconcile-session`
- Truth validation: CLI `resume-tool validate-truth`, MCP
  `resume_validate_truth`, facade capability `validate-facts`.
- Re-score: CLI `resume-tool match`, MCP `resume_check_job_match`, facade
  capability `check-resume-job-match`.

## Mode Prompt And Reason Codes

Before opening the session, ask for a review mode: `interactive`,
`review_at_end`, or `auto`. Use `review_at_end` with the underscore in command
payloads. If the user does not answer, use `interactive`.

On every `reject` or `edit` decision, offer the `EditFeedbackReasonCode` enum:

`fabrication`, `overclaim`, `unsupported`, `grammar`, `formatting`,
`not_my_voice`, `too_verbose`, `too_vague`, `wrong_emphasis`, `duplicate`,
`other`.

Pass the selected value as `--reason-code` / `reason_code`; optional free text
belongs in `--note` / `note`. For `edit`, pass final wording as
`--edited-content` / `edited_content`.

## Steps

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
4. **Open the edit session.** Prompt for mode, then call `open-edit-session`
   with the change list and any available provenance/delta data.
5. **Prompt and decide.** Use `session-prompt` then `decide-change` for each
   suggestion. Decisions are `approve`, `reject`, `edit`, or `skip`; `reject`
   and `edit` require the reason-code prompt.
6. **Commit through the hard gate.** Call `commit-session`. Stop on missing
   decisions, policy rejections, contradicted claims, or tamper detection. Do not
   apply changes manually.
7. **Validate truth.** Run **validate-facts** on the committed
   `working_path`.
8. **Report deltas.** Use the commit result or rerun `resume-tool match` /
   `resume_check_job_match` to report before/after keyword and ATS deltas. Note
   any aliases grown from accepted terminology edits.

## Truth Posture

- Only mirror wording for a skill the resume already demonstrates.
- Never turn an absent skill into a claimed skill.
- Never edit identity, employer, title-of-record, or date fields.
- Never auto-apply or bulk-write suggestions outside `commit-session`.
- Never keep a change blocked by the commit gate or truth validation.
- When in doubt, skip and route durable synonym questions through
  **learn-terminology**.

## Output

Return the committed `working_path`, session id, applied terminology changes
`{path, old, new}`, rejected/skipped suggestions with reason codes when
supplied, gate rejections, grown aliases, and before/after match deltas.
