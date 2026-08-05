---
name: inject-keywords
description: >
  Surface MISSING-BUT-TRUE keywords into the resume, truth-gated, no LLM. When a
  deterministic gap run (identify-resume-gaps) reports a JD keyword as missing
  from THIS resume but the candidate's MASTER resume proves they genuinely have
  it (an INJECTABLE keyword), this workflow adds that keyword where the candidate
  actually demonstrates it — the skills list or summary — with per-change human
  acceptance, then runs validate-resume-truth and reverts any change the truth
  gate flags, and finally reports exactly what changed and re-scores via
  check-keyword-match. It NEVER adds a keyword the candidate does not have: a
  non-injectable JD keyword stays a GAP and is routed to identify-resume-gaps,
  never fabricated in. Identity, employer, and date fields are never touched.
  Best run in a subagent.
---

# inject-keywords — read injectable gaps → agent edits → truth-gate → revert flagged → report + re-score

## Purpose

`identify-resume-gaps` scores a resume against a job **deterministically** — no
LLM. It splits each missing JD keyword into two buckets:

- **Injectable** — missing from THIS resume, but the candidate's **master resume
  proves they genuinely have it**. Surfacing it into the resume is truthful.
- **Non-injectable** — absent from both this resume and the master. This is a
  **real gap**. It is NOT a candidate for injection.

This skill's ONE job is to **surface the injectable keywords into the resume**
(the skills list or the summary), drawn ONLY from where the master resume /
evidence shows the candidate genuinely demonstrates them — truth-gated, no LLM,
per-change human acceptance. It is the safety-critical, provider-free replacement
for the disabled LLM auto-rewrite.

Distinct from **update-terminology**, which only swaps the WORDING of a keyword
the resume ALREADY satisfies. Here we ADD a TRUE keyword the resume was MISSING.
The two never overlap.

## Prerequisites gate — run this FIRST

Before doing anything, run the shared prerequisites gate defined in
[`../_shared/prerequisites.md`](../_shared/prerequisites.md). This skill's
required inputs are:

- A `ResumeDocument` JSON — the active resume (`config.json` → `active_resume`,
  under `resume-kit/resumes/`), or an explicit path the caller passed.
- A `JobDescription` JSON — the active job (`config.json` → `active_job`, under
  `resume-kit/jobs/`), or an explicit path.
- **A gap result** from `identify-resume-gaps` — the injectable vs
  non-injectable keyword split. This is what tells you which keywords are safe to
  surface. Backing the injectable list requires the **master resume / evidence**
  the gap run used; make sure it is available.

**If the resume JSON, job JSON, or a gap result is missing, wrong type, or
absent: STOP.** Do not guess, do not fabricate, do not run on partial inputs.
Name the specific upstream skill:

- Need a `ResumeDocument` JSON but only have a resume file → run **resume-to-json**.
- Need a `JobDescription` JSON but only have posting text/URL/file → run **job-to-json**.
- Need the injectable/non-injectable split → run **identify-resume-gaps** first.

Only when the resume, the job, and a gap result all resolve do you proceed.

## Run me in a subagent

This is a self-contained, file-mutating task. The main agent should **dispatch it
to a subagent** (e.g. the Task tool / a general-purpose agent), consistent with
`resume-to-json`, `job-to-json`, `manage-synonyms`, and `update-terminology`.
Hand the subagent: the paths to the resume JSON, the job JSON, the master resume
/ evidence, and the gap result (or the inputs to reproduce it), the path to
`resume-kit/config.json`, and this skill. The subagent performs the edits, gets
per-change confirmation, runs the truth gate, and returns only **what it
changed** (path, added keyword, where the master proves it) plus the re-score
delta. Do NOT stream the full resume/job/master text back into the main context.

## resume-kit working directory (file convention)

All state lives under `resume-kit/` in the current project:

```
resume-kit/
├── config.json          # pointers + preferences; holds active_resume, active_job
├── resumes/<orig-basename>-original.json
├── jobs/<orig-basename>-original.json
├── working/<session-id>/resume.json   # a revised resume is written here
└── learning/
```

If this skill writes a revised resume, save it under
`resume-kit/working/<session-id>/resume.json` and **update `config.json`'s
`active_resume`** to point at it — mirroring the `resume-to-json` convention so
downstream skills pick up the latest version.

## The surfaces this skill drives

- **The gap tool** — CLI `identify-gaps`, MCP `resume_identify_gaps`. Supplies
  the injectable vs non-injectable keyword split. (Run via **identify-resume-gaps**.)
- **The truth gate** — CLI `validate-truth`, MCP `resume_validate_truth`
  (**validate-resume-truth**). Flags any unsupported or contradicted claim. It is
  the mandatory backstop after every edit.
- **The re-score tool** — CLI `check-job-match`, MCP `resume_check_job_match`
  (**check-keyword-match**). Recomputes the keyword match so you can report the
  before/after delta.

> `resume-tool` is the CLI entrypoint (e.g. `resume-tool validate-truth ...`,
> `resume-tool check-job-match ...`).

## Steps

1. **Read the injectable list.** From the `identify-resume-gaps` result, take
   ONLY the **injectable** keywords (missing from this resume AND proven by the
   master resume / evidence). Ignore the non-injectable ones entirely — those are
   real gaps (see DON'T).
2. **For each injectable keyword, locate its truthful home in the master.**
   Confirm where the master resume / evidence genuinely demonstrates the skill.
   You are only surfacing something the candidate already has; you must be able to
   point at the master line/evidence that proves it.
3. **Propose the edit, get per-change acceptance.** For each keyword, propose
   adding it to the **skills list** or **summary** (the surfaces where a keyword
   truthfully belongs), citing the master evidence. Ask the user to
   **accept or skip each change** — never apply without an explicit "accept".
   Default is skip.
4. **Apply accepted edits to the resume JSON.** Edit ONLY the skills list /
   summary to surface the accepted keyword. Never touch identity, employer, title,
   or date fields (see DON'T).
5. **Run the truth gate.** After editing, run **validate-resume-truth**
   (`resume_validate_truth`) on the revised resume. **Revert any change it
   flags** as unsupported or contradicted — the gate's rejection is final; never
   override it, never keep a flagged change.
6. **Persist & report + re-score.** If a revised (and truth-passing) resume was
   produced, save it under `resume-kit/working/<session-id>/resume.json` and
   update `config.json`'s `active_resume`. Report a per-change log: for each
   applied change, the **path**, the **keyword added**, and **where the master
   proves it**; every change reverted by the truth gate and why; and every
   keyword skipped. Then re-score via **check-keyword-match**
   (`resume_check_job_match`) and report the **before/after keyword-match delta**.

## Truth posture — LOAD-BEARING PRODUCT POLICY (do not weaken)

The only thing this skill does is **surface a keyword the candidate GENUINELY
has** — proven by the master resume / evidence — into a resume that happened to
omit it. That is truthful. It is NOT a lever to claim skills the candidate lacks.

### DO — surface a missing-but-true keyword

- The keyword is **injectable**: missing from this resume, but the master resume
  / evidence proves the candidate demonstrates it. Add it to the skills list or
  summary, drawn from that master evidence.
- Point at the exact master line / evidence for every keyword you add — if you
  cannot, it is not injectable and you must not add it.

### DON'T — these are forbidden

- **Never add a keyword the candidate does not genuinely have.** A
  **non-injectable** keyword — absent from both this resume and the master — is a
  real **GAP**. It **stays a GAP**: surface it and route the user to
  **`identify-resume-gaps`**. **Never fabricate it into the resume** to close the
  gap. No non-injectable keyword is ever written in, under any circumstances.
- **Never edit identity, employer, title-of-record, or date fields.** This skill
  only surfaces a skill keyword into the skills list / summary; it never touches
  names, companies, titles, or dates.
- **Never keep a change the truth gate flags.** `validate-resume-truth` is
  mandatory after every edit; any flagged change is reverted, no exceptions,
  never overridden.
- **Never apply without explicit per-change acceptance**, and never auto-apply
  the whole set. Report every change you make.
- **When in doubt, skip.** If you are not confident the master genuinely proves
  the keyword for THIS candidate, do not add it — leave it for the user.

The truth gate (`validate_resume_truth`) is the backstop, not your only line of
defense: the injectable check and per-change acceptance come first, and the gate
catches anything that slips through. Honor the gate; never work around it.

## Gaps vs. keyword injection vs. terminology updates

Do not confuse these:

- **Keyword injection** (this skill) — the JD keyword is absent from THIS resume,
  but the **master resume proves the candidate genuinely has it** (injectable).
  Surfacing it into the skills list / summary is truthful. ADD a true keyword.
- **Terminology update** (`update-terminology`) — the resume ALREADY satisfies
  the JD keyword under a different surface form (alias hit). Mirroring the
  employer's exact wording is truthful. SWAP wording only.
- **Gap** (`identify-resume-gaps`) — the JD keyword is absent from both this
  resume and the master (non-injectable). A real gap: **surfaced, never rewritten
  in**.

## Output

The set of keywords actually injected — each reported as `{path, keyword, master
evidence}` — every change reverted by the truth gate (and why), every keyword
skipped, and the **before/after keyword-match delta** from the re-score. If a
revised resume was written, its path under `resume-kit/working/<session-id>/` and
the updated `active_resume` pointer. Nothing is added without explicit per-change
acceptance; no non-injectable keyword is ever written in; nothing flagged by the
truth gate is kept.
