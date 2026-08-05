---
name: inject-keywords
description: >
  Surface MISSING-BUT-TRUE keywords into the resume, truth-gated, no LLM. When a
  deterministic gap run (identify-resume-gaps) reports a JD keyword as missing
  from THIS resume but the candidate's MASTER resume proves they genuinely have
  it, this workflow creates targeted ChangeProposal records and drives the
  code-owned edit-session loop: mode prompt, per-change prompt/decision,
  commit-session hard gate, then validate-resume-truth. Direct hand-editing the
  working JSON is unsupported unless followed by reconcile-session. Best run in
  a subagent.
---

# inject-keywords - injectable gaps -> edit session -> commit gate -> truth

## Purpose

`identify-resume-gaps` scores a resume against a job deterministically. It splits
missing JD keywords into two buckets:

- **Injectable** - missing from this resume, but proven by the master resume or
  evidence. Surfacing it into this resume is truthful.
- **Non-injectable** - absent from both this resume and the master/evidence. This
  is a real gap, not an edit candidate.

This skill's job is to turn injectable keywords into targeted `ChangeProposal`
records, then drive those records through the edit-session orchestrator. The
skill does not bulk-edit resume JSON. The orchestrator owns review state,
decision logging, tamper detection, policy application, preference feedback, and
the hard write gate.

Distinct from **update-terminology**, which only swaps wording for a keyword the
resume already satisfies under an alias. Here we add a true, missing keyword to
an appropriate summary, skills, or evidence-backed accomplishment surface.

## Prerequisites Gate

Run the shared prerequisites gate in
[`../_shared/prerequisites.md`](../_shared/prerequisites.md). Required inputs:

- A `ResumeDocument` JSON: active resume from `resume-kit/config.json`, or an
  explicit path.
- A `JobDescription` JSON: active job from `resume-kit/config.json`, or an
  explicit path.
- A gap result from **identify-resume-gaps**, including the injectable and
  non-injectable split.
- The master resume/evidence used to prove each injectable keyword.

If any required input is missing, stop and name the upstream skill:

- Need a resume JSON -> run **resume-to-json**.
- Need a job JSON -> run **job-to-json**.
- Need the injectable split -> run **identify-resume-gaps**.
- Need evidence records -> run **build-candidate-evidence** or persist a user
  confirmed statement with `resume-tool add-evidence --confirmed --content ...`.

## Run Me In A Subagent

This is a self-contained improve task over potentially large resume/job/evidence
data. The main agent should hand the subagent the active resume path, job path,
master/evidence path, gap result, `resume-kit/config.json`, and this skill. The
subagent returns only the proposed/applied change summary, skipped gaps, gate
results, and before/after score deltas.

## Working Directory

All project state lives under `resume-kit/`:

```
resume-kit/
├── config.json
├── resumes/<name>-original.json
├── jobs/<name>-original.json
├── working/edit-session.json
├── working/<name>.tailored.json
└── learning/
```

The edit-session orchestrator writes the tailored resume to the `working_path`
reported by `commit-session` / `resume-tool review-edits commit`. Do not create
or overwrite that file yourself. After the session is fully committed,
downstream skills may use the committed `working_path` explicitly, or the caller
may make it active via `resume-tool set-active --resume <working_path>`.

Direct hand-editing of the working resume is unsupported because it trips tamper
detection. If the user intentionally edits the working file outside the session,
the sanctioned recovery path is `resume-tool review-edits reconcile` /
`edit_session_reconcile` / `reconcile-session`; then continue through the
session gate.

## Surfaces This Skill Drives

- Gap analysis: CLI `resume-tool identify-gaps`, MCP `resume_identify_gaps`,
  facade capability `identify-resume-gaps`.
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
  `resume_validate_truth`, facade capability `validate-resume-truth`.
- Re-score: CLI `resume-tool match`, MCP `resume_check_job_match`, facade
  capability `check-resume-job-match`.

## Mode Prompt

Before opening the session, ask the user which review mode they want:

- `interactive` - prompt and decide each change before moving on.
- `review_at_end` - collect proposals first, then review them at the end. Use
  this exact underscore spelling in CLI/MCP/capability payloads.
- `auto` - let the orchestrator auto-approve only changes its policy can safely
  apply; unsupported/deferred changes are not silently applied.

Do not choose a mode silently. If the user does not answer, use `interactive`.

## Reason Codes

On every `reject` or `edit` decision, offer the `EditFeedbackReasonCode` enum,
not open-ended free text:

`fabrication`, `overclaim`, `unsupported`, `grammar`, `formatting`,
`not_my_voice`, `too_verbose`, `too_vague`, `wrong_emphasis`, `duplicate`,
`other`.

Use `--reason-code <value>` for CLI decisions or `reason_code` for MCP/facade
calls. A short optional note is allowed through `--note` / `note`, but it never
replaces the enum. For `edit`, pass the user's final wording with
`--edited-content` / `edited_content`.

## Steps

1. **Read injectable gaps.** Use only the `injectable` keywords from
   **identify-resume-gaps**. Non-injectable keywords are reported as gaps and
   never become edit proposals.
2. **Prove each keyword.** For every injectable keyword, identify the master
   resume line or `CandidateEvidence` record proving the candidate has it. If you
   cannot point to proof, skip it.
3. **Build targeted `ChangeProposal` records.** Propose minimal `replace`,
   `append`, or `add_skill` changes against only truthful, allowed resume paths.
   Include the current `original` value when replacing text, the proposed
   `value`, and a `reason` that names the keyword and evidence. Never target
   identity, employer, title-of-record, or date fields.
4. **Open the edit session.** After the mode prompt, call `open-edit-session`
   with the change list, evidence, claim provenance, and expected score deltas
   where available. CLI example:

   ```bash
   resume-tool review-edits open \
     --mode interactive \
     --changes <changes.json> \
     --evidence <evidence.json>
   ```

5. **Present and decide through the orchestrator.** Repeatedly call
   `session-prompt` / `resume-tool review-edits prompt`, show the prompt, then
   record the user's decision with `decide-change` /
   `resume-tool review-edits decide`. Decisions must be path-correlated. Use
   `approve`, `reject`, `edit`, or `skip`; offer reason codes for `reject` and
   `edit`.
6. **Commit through the hard gate.** Call `commit-session` /
   `resume-tool review-edits commit`. If it fails because decisions are missing,
   claims are contradicted, policy rejects paths, or the working file was
   tampered with, stop and report the gate failure. Do not patch around it. If
   the user made an intentional out-of-band edit, run `reconcile-session` and
   then continue.
7. **Validate truth.** Run **validate-resume-truth** on the committed
   `working_path` with the evidence list. Any unsupported or contradicted claim
   must be resolved before export.
8. **Re-score.** Run **check-keyword-match** via `resume-tool match` /
   `resume_check_job_match`, honoring `alias_file`, and report before/after
   keyword and ATS deltas from the commit result or re-score.

## Truth Posture

- Only surface a keyword the candidate genuinely has and can prove.
- Never turn a non-injectable gap into a resume claim.
- Never edit identity, employer, title-of-record, or date fields.
- Never bulk-apply a change list or write the working JSON directly.
- Never keep a change blocked by `commit-session` or `validate-resume-truth`.
- When in doubt, skip and explain what evidence is missing.

## Output

Return the committed `working_path`, the session id, every approved/edited
change `{path, keyword, evidence}`, every rejected/skipped keyword with its
reason code when supplied, every hard-gate rejection, and the before/after match
delta. State explicitly that non-injectable gaps were not written into the
resume.
