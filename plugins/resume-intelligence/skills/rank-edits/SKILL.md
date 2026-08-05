---
name: rank-edits
description: >
  Rank truthful improvement candidates for a pending edit with the deterministic
  rank-edit-candidates surface. The skill passes candidates, FeatureContext,
  optional preferences, and alias_file to the CLI/MCP/facade surface, then
  presents the ranked candidates and reasons. It never edits the resume; chosen
  candidates must still flow through the edit-session orchestrator and hard
  commit gate. Best run in a subagent.
---

# rank-edits - candidates -> rank-edit-candidates -> present

## Purpose

The improve skills can produce several truthful candidate changes. This skill's
job is to rank those candidates with the deterministic preference-aware ranker
and present the best option(s) with reasons. It is the recommend half of the
preference-learning loop; `log-edit-feedback` records the outcome.

This skill does not edit a resume and does not bypass review. Any chosen
candidate must be represented as a `ChangeProposal` and sent through
`open-edit-session` -> `session-prompt` -> `decide-change` -> `commit-session`
before it reaches disk.

## Prerequisites Gate

Run the shared prerequisites gate in
[`../_shared/prerequisites.md`](../_shared/prerequisites.md). Required inputs:

- A `ResumeDocument` JSON.
- A `JobDescription` JSON.
- At least one truthful `Candidate` record to rank.
- A `FeatureContext` for those candidates.
- The project `alias_file` from `resume-kit/config.json`, defaulting to
  `resume-kit/learning/synonyms.json` when present.

If candidates are missing, produce them first through **inject-keywords** or
**update-terminology**. Do not invent candidates in this skill.

## Run Me In A Subagent

Ranking is read-only but may involve large candidate/context/history data. Hand
the subagent the candidate array JSON, `FeatureContext` JSON, optional
`UserPreferenceProfile` JSON, resolved `alias_file`, and this skill. The
subagent returns the ranked top candidates and reasons only.

## Working Directory

```
resume-kit/
├── config.json
└── learning/
    ├── edit-feedback.jsonl
    ├── preferences.json
    └── synonyms.json
```

Honor `alias_file`. Pass the same alias file used by `match` and
`identify-gaps`, so ranking and scoring see the same synonym universe.

## Surfaces This Skill Drives

- CLI: `resume-tool rank-edit-candidates --candidates <candidates.json>
  --context <context.json> [--profile <preferences.json>] [--alias-file <path>]`
- MCP tool: `edit_candidates_rank`
- Facade capability: `rank-edit-candidates`

Input fields are `candidates`, `context`, optional `profile`, optional
`alias_file`, and `strict`.

## Steps

1. **Confirm candidates are truthful.** Candidate generation belongs to
   **inject-keywords** or **update-terminology**. Non-injectable gaps and
   unsupported claims are never ranked.
2. **Resolve `alias_file`.** Read `resume-kit/config.json`; if it contains an
   `alias_file`, pass that path through. If absent, run seed-only.
3. **Call `rank-edit-candidates`.** Provide the candidate array, the
   `FeatureContext`, optional `UserPreferenceProfile`, and `alias_file`.
4. **Present ranked output.** Show the top candidate(s) with `candidate_id`,
   proposed text, score, and reason. Include truth-blocked candidates only as a
   count or warning, never as recommendations to apply.
5. **Route application to the edit session.** If the user chooses a candidate,
   convert it to the appropriate `ChangeProposal` and continue through the
   improve skill's edit-session flow. Do not write resume JSON here.
6. **Record the decision path.** After the user accepts, edits, rejects, skips,
   or later undoes the suggestion, run **log-edit-feedback** so future rankings
   learn from the outcome.

## Determinism

Given the same candidates, `FeatureContext`, preference profile, and alias file,
the ranking and reason strings are deterministic. Do not add LLM judgment,
network lookups, or ad hoc tie breakers.

## Output

Return the ranked top-K candidates as `{candidate_id, proposed_text, score,
reason}`, the alias file used, and any truth/policy warnings returned by the
surface. No resume file is edited by this skill.
