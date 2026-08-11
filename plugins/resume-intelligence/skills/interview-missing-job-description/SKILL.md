---
name: interview-missing-job-description
description: >
  Interactive, truth-gated interview over a job's MISSING requirements. When
  tailoring finishes and the score is still below par (or a required must-have
  is uncovered), this skill walks the user through the missing items in the
  job's own priority order — required → preferred/nice-to-have → remaining
  unmatched keywords — and elicits a durable answer for each. It NEVER inserts a
  keyword on a bare "yes": a "yes" requires a grounding fact, which is persisted
  as CandidateEvidence and routed through the existing truth-gated update-keywords
  edit-session; "no" / "not in this context" are recorded and never edit; "need
  more info" only explains and re-asks. Every durable answer is banked so future
  jobs never re-ask. Re-scores on demand. Prose orchestration — adds no core
  code. Best run in a subagent.
---

# interview-missing-job-description — elicit-and-prove, not raise-the-score

## Purpose

After tailoring and the second scoring (`check-keywords` / `resume_check_job_match`),
some gaps are not "the resume is bad" — they are requirements the resume never
mentioned but the candidate genuinely has, because we never asked. This skill
asks, truthfully.

The governing principle is **elicit-and-prove, not raise-the-score**. A "yes" is
NOT a license to insert a keyword. It is a prompt to capture a grounding fact,
persist it as evidence, and let the EXISTING truth/faithfulness gates decide
whether an edit is warranted. The interview is a new *source of claims*; it never
bypasses or weakens any gate. It reuses `analyze_keyword_gaps`, the
`update-keywords` edit-session, the `CandidateEvidence` proof surface, the
`RequirementAnswer` learning rail, and `resume_check_job_match`. It adds no core
code.

Single responsibility: drive the four-choice question loop with the correct,
distinct semantics, persist durable answers, and hand confirmed items to the
existing keyword-update path. It does not re-implement gap analysis, injection,
evidence classification, or scoring.

## When to use

Run this ONLY as the opt-in branch after the second scoring, when the user
accepts the offer to review additional requirements (offered by
`resume-workflow` when `overall < threshold` OR a required requirement is
uncovered). If the user declines, do nothing and return to final refinement.

## Prerequisites Gate

Run the shared **Prerequisites gate** first — see
[`../_shared/prerequisites.md`](../_shared/prerequisites.md). Required inputs:

- An active **`ResumeDocument` JSON** — the `active_resume` pointer in
  `resume-kit/config.json` (or an explicit path).
- An active **`JobDescription` JSON** — the `active_job` pointer in
  `resume-kit/config.json` (or an explicit path).
- A **`KeywordGapAnalysis`** for this resume↔job pair from **check-gaps**
  (CLI `resume-tool identify-gaps`, MCP `resume_identify_gaps`), used only for
  the `missing` keyword slice that has no matching `Requirement`.
- A **master `ResumeDocument`** (or its configured pointer) so `check-gaps` /
  gap analysis can classify injectability for the update step.

If any required input is missing, STOP and name the upstream skill — resume →
**parse-resume**; job → **parse-job**; gap split → **check-gaps**. Do not guess
and do not run on partial input.

## Run Me In A Subagent

This is a self-contained interactive loop over potentially large resume/job/gap
data. The main agent hands the subagent the active resume path, job path, master
path, the `KeywordGapAnalysis`, `resume-kit/config.json`, and this skill. The
subagent returns only: the durable answers recorded, evidence captured, changes
proposed/applied through `update-keywords` with their gate results, and any
before/after score deltas.

## Surfaces this skill drives (all existing — no new surface)

- **Gap analysis**: CLI `resume-tool identify-gaps`, MCP `resume_identify_gaps`
  (facade `check-gaps`) → `KeywordGapAnalysis`.
- **Answer memory (T1 rail — RIT-T-0157)**: CLI `resume-tool requirement-answer`,
  MCP `mcp__resume-kit__requirement_answer_record` (facade `requirement-answer`).
  Write a `RequirementAnswer` with `--answer <record.json>`; pre-filter with
  `--query-key <normalized_key> [--query-context-tag <tag>]`. The result carries
  `already_answered` (the deterministic `is_already_answered` verdict). The
  `requirement_key` is the shared matching normalization (`surface_form`) of the
  requirement/keyword text; do NOT invent a second normalization.
- **Evidence (proof for a "yes")**: CLI `resume-tool add-evidence --confirmed
  --content <fact> --kind user_statement [--tag <term>] --update-active`, MCP
  `mcp__resume-kit__candidate_evidence_add`. This persists a `CandidateEvidence`
  with `user_confirmed: true` and (via `--update-active`) points
  `config.active_evidence` at it, so the confirmed fact is folded into the
  master-equivalent proof surface `analyze_keyword_gaps` consults (RIT-T-0158) —
  a confirmed "yes" thereby becomes *injectable* through the existing route, with
  no new proof path.
- **Truth-gated edit**: the **update-keywords** skill and the shared
  change-application runbook ([`../_shared/apply-changes.md`](../_shared/apply-changes.md))
  — owns the edit-session open/prompt/decide loop, the `commit-session` hard
  gate, and `validate-facts`.
- **Re-score**: CLI `resume-tool match`, MCP `resume_check_job_match` — via the
  **check-keywords** skill.

## Step 1 — Build the question queue (JD priority order, NO ranking)

Read the active `JobDescription` and the `KeywordGapAnalysis`. Build ONE ordered
queue, and never re-order it by relevance or "worth asking" — the JD's own order
is the order:

1. **REQUIRED requirements first** — `JobDescription.requirements`
   (`RequirementKind.REQUIRED`) whose keywords are still missing (not matched by
   the resume, honoring the alias file).
2. **PREFERRED / nice-to-have next** — `JobDescription.qualifications`
   (`RequirementKind.PREFERRED`) whose keywords are still missing.
3. **Remaining unmatched keywords last** — entries in the
   `KeywordGapAnalysis.missing` set that are not already covered by a queued
   `Requirement` above (job `keywords` not tied to a listed requirement).

One requirement/keyword per queue entry. Preserve JD document order within each
tier. Do not score, rank, or drop items for "relevance" — that is an explicit
non-goal.

## Step 2 — Pre-filter with the T1 rail (skip already-answered)

Before asking each queued item, compute its `requirement_key` (the `surface_form`
normalization of the requirement/keyword text) and its coarse `context_tag`
(Step 4), then query the rail:

```
resume-tool requirement-answer --query-key <requirement_key> \
    [--query-context-tag <context_tag>] --output json
```

Act on `already_answered`:

- `"yes"` or `"no"` → **skip** (durable, global). Do not re-ask.
- `"not_in_context"` → **skip only when this job's `context_tag` matches** the
  recorded one; otherwise the context differs → **ask**.
- `null` → **ask**.

Err toward asking: a differing or absent context tag means eligible-to-ask. This
is exactly the `is_already_answered` dedupe rule — do not re-implement it; trust
the rail's verdict.

## Step 3 — Ask one requirement with exactly four choices

Present the requirement plainly and offer exactly these four responses. Do NOT
lead the user toward "yes" — state the requirement neutrally and let them answer.

Present the four labeled choices:

1. **Yes — I have this**
2. **No — I don't have this**
3. **Need more info** (explain what this requirement means)
4. **Not in this context** (I have it, but not for a role like this)

### Choice: No
The candidate does not have this — a durable, global negative. Persist and make
no edit:

```
resume-tool requirement-answer \
    --answer <RequirementAnswer{requirement_key, answer:"no", ts}.json>
```

Do not propose any resume change. Move to the next queue item.

### Choice: Yes — REQUIRES a grounding fact (a bare "yes" is NOT accepted)
Do not accept a boolean "yes." Ask for a concrete grounding fact — **where /
when / what you did / scale or outcome if known** (e.g. "At Acme 2022–2023, ran
our prod EKS cluster, ~40 services"). If the user cannot give a grounding fact,
treat it as unproven: do NOT persist a "yes", do NOT edit — re-ask or let them
choose another response. Never fabricate or embellish the fact for them.

Once a real grounding fact is given, in order:

1. **Persist the evidence** as a user-confirmed `CandidateEvidence` and fold it
   into the active proof surface:
   ```
   resume-tool add-evidence --confirmed --content "<the user's grounding fact>" \
       --kind user_statement --tag "<requirement term>" --update-active
   ```
   Capture the returned evidence `id` for `evidence_ref`.
2. **Persist the answer** on the rail with the evidence link:
   ```
   resume-tool requirement-answer \
       --answer <RequirementAnswer{requirement_key, answer:"yes",
                 evidence_ref:<evidence id>, ts}.json>
   ```
3. **Propose the truthful edit.** Hand the now-injectable term to the
   **update-keywords** path: re-run **check-gaps** (which now reads the confirmed
   evidence as master-equivalent proof, so the term is classified `injectable`),
   then follow **update-keywords** end to end — targeted `ChangeProposal`s, the
   edit-session, the `commit-session` hard gate, and `validate-facts`. The edit
   must still pass every existing gate; if the gate rejects it, the evidence and
   answer still stand — the keyword simply is not written in.

Never write the keyword in directly and never bypass the edit-session/commit
gate. The interview supplies the proof; the existing gate decides the edit.

### Choice: Need more info — EXPLAIN, do not answer for them
This is an explanation state, not an answer. Explain what the requirement means
in plain terms (what the skill/experience actually is), WITHOUT coaching the user
toward "yes" and without hinting at what answer would help the score. Then loop
back to the SAME question with the same four choices. Guidance:

- Do NOT persist anything durable (no `RequirementAnswer`). At most log it as
  interaction telemetry.
- Do NOT suppress future asks — this item stays eligible.
- Do NOT nudge: explaining "Kubernetes is a container orchestrator" is fine;
  "you probably have this if you've used Docker" is coaching and is forbidden.

### Choice: Not in this context — a context-scoped "no"
The candidate has it, but not for a role like this one (e.g. management
experience declined for a senior-IC posting). Persist a context-scoped negative;
make no edit:

```
resume-tool requirement-answer \
    --answer <RequirementAnswer{requirement_key, answer:"not_in_context",
              context_tag:<this job's tag>, ts}.json>
```

This suppresses re-asking ONLY on an exact key match AND a matching `context_tag`
(Step 4). A materially different future context is eligible to ask again.

## Step 4 — Derive the coarse context tag (`not_in_context`)

For `not_in_context` answers and the pre-filter, derive ONE coarse, deterministic
context tag from the active JD — a low-cardinality role/industry label such as
`role:ic`, `role:manager`, or `industry:fintech`. Keep it coarse so it groups
"materially similar" postings; do not encode company- or posting-specific detail.
Use the same derivation on the query side (Step 2) and the write side so tags
compare equal. It is only meaningful for `not_in_context`; leave `context_tag`
unset for `yes`/`no`.

## Step 5 — Cadence controls

- **Every 4 questions**, pause and offer: **re-check the score, or continue?**
  On re-check, run **check-keywords** (`resume-tool match` /
  `resume_check_job_match`) and show the coverage/score.
- **Whenever a score is shown**, offer: **continue questioning, or move on to
  final refinement?**

Respect the cadence rather than dumping the whole queue; if the queue is large,
the every-4 checkpoint keeps the interview legible and avoids re-ask fatigue.

## Step 6 — Termination

The loop ends when ANY of:

- the re-scored `overall` crosses the configured threshold, OR
- the user declines to continue, OR
- the queue is exhausted (no more unanswered items).

On termination, hand control back to the EXISTING final-refinement step
(the `perfect` / refinement stage in `resume-workflow`). Do **not** auto-finalize,
auto-export, or force any further step — the user chose when to stop.

## Truth Posture (cross-cutting, non-negotiable)

- **Never coach toward "yes."** State requirements neutrally; "need more info"
  explains, it does not lead the witness.
- **Never accept a bare "yes."** A grounding fact is mandatory before any evidence
  or answer is persisted for a "yes."
- **Never fabricate or embellish evidence.** Persist only what the user actually
  attested to, verbatim in substance.
- **Every resulting edit still passes the existing truth/faithfulness gate.** The
  interview adds a source of claims; it never bypasses `commit-session` /
  `validate-facts`.
- **A real gap stays a gap.** A "no" / unproven item is honestly reflected in the
  score; it is not aliased or written away.

## Output

Return: the ordered queue processed, each item's recorded answer
(`yes`/`no`/`not_in_context` or "explained & re-asked"), evidence captured with
its `evidence_ref` for each "yes", the `update-keywords` gate results and any
committed change deltas, before/after re-score deltas at each checkpoint, and the
termination reason. State explicitly which items were declined or left unproven
and therefore produced no edit.
