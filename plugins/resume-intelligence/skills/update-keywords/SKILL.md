---
name: update-keywords
description: >
  Update MISSING-BUT-TRUE keywords into the resume, truth-gated, no LLM. When a
  deterministic gap run (check-gaps) reports a JD keyword as missing
  from THIS resume but the candidate's MASTER resume proves they genuinely have
  it, this workflow creates targeted ChangeProposal records and drives the
  code-owned edit-session loop: mode prompt, per-change prompt/decision,
  commit-session hard gate, then validate-facts. Direct hand-editing the
  working JSON is unsupported unless followed by reconcile-session. Best run in
  a subagent.
---

> **Renamed:** `update-keywords` was `inject-keywords` before v1.0.0 (see RIT-A-0005).

# update-keywords - injectable gaps -> edit session -> commit gate -> truth

## Purpose

`check-gaps` scores a resume against a job deterministically. It splits
missing JD keywords into two buckets:

- **Injectable** - missing from this resume, but proven by the master resume or
  evidence. Surfacing it into this resume is truthful.
- **Non-injectable** - absent from both this resume and the master/evidence. This
  is a real gap, not an edit candidate.

This skill's job is the **create-change** step: turn injectable keywords into
targeted `ChangeProposal` records. It then hands those records to the shared
change-application runbook, which owns the decide → commit-gate → validate → learn
spine. The skill does not bulk-edit resume JSON.

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
- A gap result from **check-gaps**, including the injectable and
  non-injectable split.
- The master resume/evidence used to prove each injectable keyword.

If any required input is missing, stop and name the upstream skill:

- Need a resume JSON -> run **parse-resume**.
- Need a job JSON -> run **parse-job**.
- Need the injectable split -> run **check-gaps**.
- Need evidence records -> run **extract-evidence** or persist a user
  confirmed statement with `resume-tool add-evidence --confirmed --content ...`.

## Run Me In A Subagent

This is a self-contained improve task over potentially large resume/job/evidence
data. The main agent should hand the subagent the active resume path, job path,
master/evidence path, gap result, `resume-kit/config.json`, and this skill. The
subagent returns only the proposed/applied change summary, skipped gaps, gate
results, and before/after score deltas.

## Surface This Skill Drives (create-change input)

- Gap analysis: CLI `resume-tool identify-gaps`, MCP `resume_identify_gaps`,
  facade capability `check-gaps`.

The edit-session, truth-validation, and re-score surfaces are owned by the shared
runbook (see below).

## Steps (create-change)

1. **Read injectable gaps.** Use only the `injectable` keywords from
   **check-gaps**. Non-injectable keywords are reported as gaps and
   never become edit proposals.
2. **Prove each keyword.** For every injectable keyword, identify the master
   resume line or `CandidateEvidence` record proving the candidate has it. If you
   cannot point to proof, skip it.
3. **Build targeted `ChangeProposal` records.** Propose minimal `replace`,
   `append`, or `add_skill` changes against only truthful, allowed resume paths.
   Include the current `original` value when replacing text, the proposed
   `value`, and a `reason` that names the keyword and evidence. Never target
   identity, employer, title-of-record, or date fields.

## Apply the changes

Hand the `ChangeProposal` records to the shared change-application runbook and
follow it end to end:
[`../_shared/apply-changes.md`](../_shared/apply-changes.md). It owns mode
selection, the open/prompt/decide loop and reason codes, the `commit-session`
hard gate, `validate-facts`, the automatic learn tail, and the re-score. Pass the
evidence list so `validate-facts` can confirm each injected keyword; re-score with
**check-keywords**.

## Truth Posture

Follow the shared truth posture in the runbook, plus:

- Only surface a keyword the candidate genuinely has and can prove.
- Never turn a non-injectable gap into a resume claim.

## Output

Return the runbook's standard output (committed `working_path`, session id,
decided changes, gate rejections, before/after match delta) with each approved/
edited change carrying its `{path, keyword, evidence}`, and every rejected/skipped
keyword with its reason code when supplied. State explicitly that non-injectable
gaps were not written into the resume.
