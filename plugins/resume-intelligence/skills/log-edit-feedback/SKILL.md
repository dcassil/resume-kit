---
name: log-edit-feedback
description: >
  Record the user's outcome for an in-flight edit suggestion so preference
  learning improves — no LLM. When the user has just accepted, accepted-with-
  modifications, rejected, or undone a presented edit, this workflow writes one
  append-only EditFeedback record (with an optional reason and the whole-term
  diff between proposed and final text via diff_terms) to
  `resume-kit/learning/edit-feedback.jsonl`, stores the PreferencePair implied by
  the outcome, and refreshes `resume-kit/learning/preferences.json` by
  re-deriving the preference profile from the full log. It is the record-the-
  outcome half of the preference-learning loop (rank-edits is the recommend
  half). This is an AGENT-DRIVEN workflow: the resume_kit_feedback package has NO
  CLI or MCP surface, so the agent drives its deterministic Python API directly.
  Gated on an in-flight suggestion. Best run in a subagent.
---

# log-edit-feedback — record outcome → store preference pair → refresh preferences

## Purpose

Preference learning only improves if outcomes are recorded. This skill's ONE job
is to **record what the user decided about a presented edit** and update the
learned preferences accordingly. It is the write half of the loop; `rank-edits`
is the read/recommend half.

It records exactly ONE outcome per run for ONE in-flight suggestion:
`accepted`, `accepted_modified`, `rejected`, or `undone`, plus an optional
free-text reason and (for a kept edit) the whole-term diff between the proposed
text and what the user actually kept.

**Agent-driven, no CLI/MCP surface.** The `resume_kit_feedback` package exposes
NO `resume-tool` CLI command and NO MCP tool. There is nothing to shell out to.
The agent drives the package's deterministic Python API directly. Everything is
pure and offline: no clock, no network, no LLM. Timestamps and `now` are DATA the
agent supplies — the package never reads the clock.

## Prerequisites gate — run this FIRST

Before doing anything, run the shared prerequisites gate defined in
[`../_shared/prerequisites.md`](../_shared/prerequisites.md), then confirm this
skill's specific gate:

- **An in-flight suggestion.** There must be a suggestion the user has just acted
  on — normally one presented by `rank-edits`, or an edit applied by
  `inject-keywords` / `update-terminology`. You need its `section`, `edit_type`,
  `original_text`, `proposed_text`, the `target_terms` it surfaced, and the
  resume/job identifiers it applied to.
- **The user's outcome** for that suggestion: one of `accepted`,
  `accepted_modified`, `rejected`, `undone`.

**If there is no in-flight suggestion, or no decided outcome for it: STOP.** Do
not invent a suggestion, do not guess an outcome, do not write a record for an
edit the user never saw. If the user wants a recommendation first, route them to
**rank-edits**; only log an outcome once a real suggestion has a real decision.

## Run me in a subagent

This is a self-contained, file-mutating task that drives a Python API. The main
agent should **dispatch it to a subagent** (e.g. the Task tool / a
general-purpose agent), consistent with `rank-edits`, `inject-keywords`, and
`manage-synonyms`. Hand the subagent: the in-flight suggestion's fields, the
user's outcome (+ optional reason + final text), the path to
`resume-kit/config.json`, and this skill. The subagent appends the record,
refreshes preferences, and returns only **what it logged** (outcome, term diff,
the refreshed preference summary). Do NOT stream the full resume/job/log text
back into the main context.

## resume-kit working directory (file convention)

All state lives under `resume-kit/` in the current project:

```
resume-kit/
├── config.json
├── resumes/<orig-basename>-original.json
├── jobs/<orig-basename>-original.json
└── learning/
    ├── edit-feedback.jsonl   # THIS skill's append target (RIT-T-0085 format)
    └── preferences.json      # refreshed here after each logged outcome (RIT-T-0086)
```

## The Python API this skill drives (`resume_kit_feedback`)

All pure and offline. The relevant surface (imported from the
`resume_kit_feedback` package root):

- `diff_terms(proposed, final) -> (preserved, removed, added)` — deterministic
  whole-term diff; use it to fill an `accepted_modified` record's
  `preserved_terms` / `removed_terms` / `added_terms`.
- `append_edit_feedback(record, *, base_path=...)` — append ONE `EditFeedback`
  record as a single JSON line to `learning/edit-feedback.jsonl`. Append-only;
  it never rewrites or reorders prior lines.
- `read_edit_feedback(*, base_path=...)` — read the full log back (needed to
  re-derive preferences over the complete history).
- `derive_preferences(records, *, now, base_path=...)` — re-derive and PERSIST
  the `UserPreferenceProfile` to `learning/preferences.json`. `now` is DATA (a
  caller-supplied ISO-8601 string), NOT the wall clock.

The `EditFeedback` schema (from `resume_kit_schemas`) carries: `edit_id`,
`resume_id`, `job_id`, `section`, `edit_type`, `original_text`, `proposed_text`,
`final_text` (None when rejected/undone), `target_terms`,
`matched_job_requirements`, `predicted_ats_gain`, `confidence`, `outcome`,
`rejection_reason` (optional), `edit_distance` (optional),
`preserved_terms` / `removed_terms` / `added_terms`, and a caller-supplied
`timestamp`. The `PreferencePair` schema carries `preferred_candidate`,
`rejected_candidate`, `strength`.

## Steps

1. **Gather the outcome.** Confirm the in-flight suggestion and the user's
   decision: `accepted`, `accepted_modified`, `rejected`, or `undone`. Ask for an
   optional short reason (store it in `rejection_reason` for a rejection/undo).
2. **Compute the term diff (kept edits).** For `accepted` (kept as proposed) the
   final text equals `proposed_text`. For `accepted_modified`, take the user's
   final text and call `diff_terms(proposed_text, final_text)` to fill
   `preserved_terms` / `removed_terms` / `added_terms`. For `rejected` / `undone`
   there is no kept text — set `final_text=None`.
3. **Build and append the record.** Construct one `EditFeedback` with a stable
   `edit_id`, the suggestion's fields, the computed outcome + diff, and a
   caller-supplied ISO-8601 `timestamp` (DATA — you provide it; the package never
   reads a clock). Call `append_edit_feedback(record,
   base_path=<resume-kit dir>)`.
4. **Store the PreferencePair.** Record the comparison the outcome implies — the
   candidate the user preferred vs the one they rejected, with a `strength` that
   reflects how strong the signal is (an `undone` outcome is a stronger negative
   than an up-front `rejected`). Persist it alongside the log so ranking is
   conceptually trained-by-comparison. When there is no explicit competing
   candidate, pair the presented candidate against a "no-edit" / status-quo
   baseline id so the direction of preference is still captured.
5. **Refresh preferences.** Read the full log back with `read_edit_feedback` and
   call `derive_preferences(records, now=<ISO now>, base_path=<resume-kit dir>)`
   to re-derive and re-persist `learning/preferences.json`. Use a single explicit
   `now` for the run so the refresh is reproducible.
6. **Report.** State exactly what was logged (outcome, term diff, reason if any)
   and summarize how the refreshed profile changed (new accepted/rejected
   phrases, tone/length/strength shifts, confidence).

## Determinism & append-only integrity

- **Append-only.** `append_edit_feedback` only ever appends; prior lines are
  never rewritten or reordered. Never edit or delete existing log lines.
- **Timestamps are DATA.** You supply the record `timestamp` and the
  `derive_preferences` `now`; the package never reads the clock. Given the same
  log and the same `now`, the refreshed `preferences.json` is IDENTICAL run to
  run — logging the same outcome twice against the same `now` produces a
  deterministic profile.
- **Undone weighs heavier.** An `undone` outcome (the user first accepted, then
  reversed) is a stronger negative signal than an up-front `rejected`; reflect
  that in the `PreferencePair` `strength` and let `derive_preferences` apply its
  documented undone weighting.

## Output

A confirmation of the single outcome logged — `{edit_id, outcome, reason?,
preserved/removed/added terms}` — the stored `PreferencePair`, and a short
summary of how `preferences.json` changed after re-derivation. Nothing else is
edited; the resume itself is untouched by this skill.
