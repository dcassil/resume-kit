---
name: learn-change
description: >
  Learn the user's outcome for an in-flight edit suggestion through the
  record-edit-feedback surface, then refresh preferences. Uses the structured
  EditFeedbackReasonCode enum plus an optional note, and records a PreferencePair
  when the outcome implies a preferred-vs-rejected comparison. No LLM required.
  Best run in a subagent.
---

> **Renamed:** `learn-change` was `log-edit-feedback` before v1.0.0 (see RIT-A-0005).


# learn-change - record outcome -> preference pair -> refresh preferences

## Purpose

Preference learning improves only when outcomes are recorded. This skill writes
one `EditFeedback` record for one real edit suggestion the user saw, optionally
writes the `PreferencePair` implied by that outcome, then refreshes
`resume-kit/learning/preferences.json`.

Use this for outcomes from `rank-changes` recommendations or edit-session
decisions from **update-keywords** / **update-terminology**. Do not log
speculative edits the user never saw.

## Prerequisites Gate

Run the shared prerequisites gate in
[`../_shared/prerequisites.md`](../_shared/prerequisites.md), then confirm:

- There is one in-flight suggestion or committed edit decision.
- The user outcome is known: `accepted`, `accepted_modified`, `rejected`, or
  `undone`.
- You have the fields needed for `EditFeedback`: edit id, resume id, job id,
  section, edit type, original text, proposed text, final text when kept, target
  terms, matched job requirements, predicted ATS gain, confidence, and timestamp.

If there is no real suggestion and no user outcome, stop. Route the user to
**rank-changes** or the edit-session loop first.

## Reason Codes

For `accepted_modified`, `rejected`, and `undone`, offer the
`EditFeedbackReasonCode` enum:

`fabrication`, `overclaim`, `unsupported`, `grammar`, `formatting`,
`not_my_voice`, `too_verbose`, `too_vague`, `wrong_emphasis`, `duplicate`,
`other`.

Store the selected enum as `reason_code`. A short optional note is allowed as
`reason_note`; do not use legacy free-text-only rejection reasons for new
records.

## Surfaces This Skill Drives

- CLI: `resume-tool record-edit-feedback --feedback <feedback.json>
  [--preference-pair <pair.json>] [--base-path <resume-kit>]`
- MCP tool: `edit_feedback_record`
- Facade capability: `record-edit-feedback`
- Preference refresh CLI: `resume-tool refresh-preferences --now <iso>
  [--records <records.json>] [--base-path <resume-kit>]`
- Preference refresh MCP tool: `preferences_refresh`
- Preference refresh facade capability: `refresh-preferences`

## Steps

1. **Gather the outcome.** Confirm exactly one suggestion and one outcome:
   `accepted`, `accepted_modified`, `rejected`, or `undone`.
2. **Collect the structured reason when needed.** For modify/reject/undo, ask
   the user to choose one `EditFeedbackReasonCode`; collect an optional note only
   after the enum is chosen.
3. **Build `EditFeedback`.** Use `final_text=proposed_text` for `accepted`, the
   user's final text for `accepted_modified`, and `final_text=null` for
   `rejected`/`undone`. Fill `reason_code`, optional `reason_note`,
   `preserved_terms`, `removed_terms`, and `added_terms` when known. The
   timestamp is caller-supplied data.
4. **Build `PreferencePair` where applicable.** When the outcome compares two
   candidates, record the kept candidate as `preferred_candidate` and the
   rejected candidate as `rejected_candidate`. When there is no explicit
   competitor, compare the presented candidate against a stable status-quo /
   no-edit baseline id. Use a stronger signal for `undone` than for an up-front
   rejection.
5. **Call `record-edit-feedback`.** Pass the feedback JSON and optional
   preference-pair JSON through the CLI, MCP tool, or facade capability.
6. **Refresh preferences.** Call `refresh-preferences` with a caller-supplied
   ISO `--now` value so `learning/preferences.json` is re-derived from the log.
7. **Report.** Return `{edit_id, outcome, reason_code, reason_note?}`, any
   `PreferencePair` written, and the refreshed preference summary.

## Append-Only Integrity

Feedback history is append-only. Do not edit or delete old
`learning/edit-feedback.jsonl` rows in agent code. If a prior edit is reversed,
log a new `undone` outcome.

## Output

Confirm the single logged outcome, the enum reason when supplied, the optional
note, the `PreferencePair` if one was recorded, and the preference refresh
result. The resume itself is untouched by this skill.
