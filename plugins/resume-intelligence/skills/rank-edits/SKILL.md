---
name: rank-edits
description: >
  Rank the truthful improvement candidates for a pending edit and PRESENT the
  best one(s) with an explanation — human-in-loop, never auto-applies. For a
  pending improvement, this workflow ENUMERATES the truthful candidate edits the
  improve skills (inject-keywords / update-terminology) would produce, retrieves
  the deterministic Preference-RAG context from past outcomes, extracts
  per-candidate features (ATS/keyword gain, unsupported-claim risk, voice match,
  specificity, historical success), and RANKS them with the explainable
  HeuristicRanker. Truth-failing candidates are HARD-BLOCKED — a fabricated claim
  can never be surfaced. It presents the top candidate(s) with the reason; the
  user chooses which (if any) to apply via the truth-gated improve skills. This
  is an AGENT-DRIVEN workflow: the resume_kit_feedback package has NO CLI or MCP
  surface, so the agent computes ranking by driving the package directly. Honors
  `alias_file`. Best run in a subagent.
---

# rank-edits — enumerate truthful candidates → RAG → features → rank → present with explanation

## Purpose

The improve skills (`inject-keywords`, `update-terminology`) each know how to
produce truthful edits, but when several candidate edits are available for a
pending improvement, which should the user see first? This skill's ONE job is to
**rank the truthful candidate edits and present the best one(s) with a plain
explanation**, so the user can pick knowingly. It is the read-and-recommend half
of the preference-learning loop; `log-edit-feedback` is the record-the-outcome
half.

**Human-in-loop, never auto-applies.** This skill PRESENTS ranked candidates and
their reasons. It does NOT edit the resume. The user decides which candidate to
apply, and application happens through the existing truth-gated improve skills
(`inject-keywords` / `update-terminology`) — the same safety gates as always.

**Agent-driven, no CLI/MCP surface.** Unlike the scoring skills, the
`resume_kit_feedback` package exposes NO `resume-tool` CLI command and NO MCP
tool. There is nothing to shell out to. Instead the agent drives the package's
deterministic Python API directly (in a subagent or a small inline step), feeding
it the candidates + past feedback + preference profile as DATA. Everything the
package computes is pure and offline: no clock, no network, no LLM — identical
inputs always yield an identical ranking and identical reason strings.

## Prerequisites gate — run this FIRST

Before doing anything, run the shared prerequisites gate defined in
[`../_shared/prerequisites.md`](../_shared/prerequisites.md). This skill's
required inputs are:

- A `ResumeDocument` JSON — the active resume (`config.json` → `active_resume`,
  under `resume-kit/resumes/`), or an explicit path the caller passed.
- A `JobDescription` JSON — the active job (`config.json` → `active_job`, under
  `resume-kit/jobs/`), or an explicit path.
- **The candidate edits to rank** — the set of truthful candidate edits produced
  by the improve skills for the pending improvement (see "Enumerate candidates"
  below). If you have no candidates yet, produce them first via
  `inject-keywords` / `update-terminology`; do NOT invent candidates here.

**If the resume JSON, job JSON, or the candidate set is missing, wrong type, or
absent: STOP.** Do not guess, do not fabricate a candidate, do not run on partial
inputs. Name the specific upstream skill:

- Need a `ResumeDocument` JSON but only have a resume file → run **resume-to-json**.
- Need a `JobDescription` JSON but only have posting text/URL/file → run **job-to-json**.
- Need the injectable/non-injectable split to enumerate candidates → run
  **identify-resume-gaps** first.
- Need candidate edits → produce them via **inject-keywords** / **update-terminology**.

Only when the resume, the job, and at least one candidate all resolve do you
proceed.

## Run me in a subagent

This is a self-contained, read-and-recommend task that drives a Python API over
possibly-large resume/job/feedback data. The main agent should **dispatch it to a
subagent** (e.g. the Task tool / a general-purpose agent), consistent with
`inject-keywords`, `update-terminology`, and `manage-synonyms`. Hand the
subagent: the paths to the resume JSON, the job JSON, the candidate set (or the
inputs to reproduce it), the path to `resume-kit/config.json` (for `alias_file`),
and this skill. The subagent runs the ranking and returns only the **ranked
top-K candidates with their reasons** (plus which, if any, were truth-blocked).
Do NOT stream the full resume/job/feedback text back into the main context.

## resume-kit working directory (file convention)

All state lives under `resume-kit/` in the current project:

```
resume-kit/
├── config.json          # pointers + preferences; holds active_resume, active_job, alias_file
├── resumes/<orig-basename>-original.json
├── jobs/<orig-basename>-original.json
├── working/<session-id>/resume.json
└── learning/
    ├── edit-feedback.jsonl   # past outcomes (append-only, RIT-T-0085 format)
    ├── preferences.json      # derived preference profile (RIT-T-0086)
    └── synonyms.json         # alias index (alias_file); honored when enumerating candidates
```

**Honor `alias_file`.** Read `config.json`'s `alias_file` (default
`resume-kit/learning/synonyms.json`). Terminology candidates must be enumerated
under the SAME alias index the scoring skills use, so what you rank matches what
the deterministic engine sees. Pass it through to `update-terminology` /
`identify-resume-gaps` exactly as those skills document.

## The Python API this skill drives (`resume_kit_feedback`)

This skill orchestrates the deterministic preference-learning package. All of it
is pure: it never reads the clock, the network, or an LLM. The relevant surface:

- Log I/O — `read_edit_feedback(*, base_path=...)` returns the past
  `EditFeedback` records from `learning/edit-feedback.jsonl`.
- Preferences — `derive_preferences(records, *, now, base_path=...)` returns the
  `UserPreferenceProfile`. `now` is DATA (a caller-supplied ISO-8601 string), NOT
  the wall clock — supply the same `now` you want the derivation anchored to.
- Retrieval — `retrieve_preference_context(context, records, profile, *, k=3)`
  where `context` is an `EditContext(section, target_terms, edit_type,
  aggressiveness)`. Returns a `PreferenceContext` (accepted/rejected exemplars +
  an injectable `summary`).
- Features + ranking — build a `FeatureContext(resume, job, evidence, history)`
  and a list of `Candidate(candidate_id, section, proposed_text, original_text,
  edit_type, target_terms)`, then call
  `HeuristicRanker().rank(candidates, context, *, profile)`. It returns
  `list[RankedCandidate]` (each carrying `candidate`, `features`, `score`, and a
  human-readable `reason`), best-first, with truth-failing candidates already
  excluded.

Import these from the `resume_kit_feedback` package root.

## Steps

1. **Enumerate truthful candidates.** For the pending improvement, list the
   candidate edits the improve skills would produce — each a `Candidate` with a
   stable `candidate_id`, its `section`, the `proposed_text` (and `original_text`
   for a swap), an `edit_type` label, and the `target_terms` it surfaces:
   - **Keyword-injection candidates** come from the `identify-resume-gaps`
     **injectable** list (missing-but-true keywords the master resume proves), as
     `inject-keywords` documents. Non-injectable keywords are real gaps — NEVER
     enumerate them as candidates.
   - **Terminology candidates** come from `update-terminology`'s alias-satisfied
     suggestions under `alias_file` (surface-wording swaps for a skill the resume
     already has).
   Every candidate must be one the improve skills could truthfully apply. Do not
   fabricate a candidate for a skill the resume/master does not support.
2. **Read past outcomes.** Call `read_edit_feedback(base_path=<resume-kit dir>)`
   to load the `EditFeedback` history. An empty/missing log is fine (empty list).
3. **Derive preferences.** Call `derive_preferences(records, now=<ISO now>,
   base_path=<resume-kit dir>)`. Use a single, explicit `now` value for the run
   (DATA, not the clock) so the result is reproducible.
4. **Retrieve Preference-RAG context.** Build an `EditContext` describing the
   pending edit (section, target_terms, edit_type, intended aggressiveness) and
   call `retrieve_preference_context(context, records, profile, k=3)`. Keep its
   `summary` to show alongside the recommendation.
5. **Rank.** Build the `FeatureContext(resume, job, evidence, history=records)`
   and call `HeuristicRanker().rank(candidates, context, profile=profile)`. The
   ranker extracts each candidate's features, HARD-BLOCKS any truth-failing
   candidate (see below), and returns the survivors best-first with a `reason`.
6. **Present the top candidate(s) WITH the explanation.** Show the user the top
   candidate (optionally the top few) — its `proposed_text`, its `score`, and its
   `reason` string (which names the driving features), plus the retrieved
   preference `summary` for context. Make clear this is a recommendation.
7. **Hand off — never apply here.** Ask the user which candidate (if any) to
   apply. Route the chosen one to the matching truth-gated improve skill
   (`inject-keywords` for an injection, `update-terminology` for a wording swap),
   which performs the edit under its own per-change acceptance + truth gate. This
   skill itself edits nothing.
8. **Offer to log the outcome.** After the user accepts / modifies / rejects a
   presented candidate, offer to run **log-edit-feedback** to record the outcome
   so future rankings improve.

## Truth hard-block — LOAD-BEARING PRODUCT POLICY (do not weaken)

The ranker EXCLUDES any candidate whose `unsupported_claim_risk` reaches the
truth-gate failure threshold BEFORE scoring — a candidate-only truth-gate failure
sets that risk to the block level, so a fabricated claim can never appear in the
ranked output regardless of how strong its ATS/keyword/voice signals are. Do NOT
override this, do NOT surface a truth-blocked candidate "for completeness", and
do NOT lower the threshold. If every candidate is blocked, report that there is
nothing truthful to recommend and route the user to `identify-resume-gaps` for
the real gaps — never paper a gap over with a fabricated candidate.

The ranking is multi-objective (predicted acceptance, ATS gain, keyword gain,
fact-support, voice, specificity, section fit, minus repetition/length) with
transparent, documented weights — never acceptance alone — so the reason you
present to the user honestly reflects why a candidate ranked where it did.

## Determinism

Given the same candidates, the same feedback log, the same preference profile,
and the same `now`, the ranking, the scores, and every reason string are
IDENTICAL run to run. When you want a reproducible recommendation, pin `now` and
reuse the same candidate set; do not re-enumerate candidates in a different order
and expect a different ranking (ties break on `candidate_id`, so order-in is
irrelevant to order-out).

## Output

The ranked top-K truthful candidates — each reported as `{candidate_id,
proposed_text, score, reason}` — plus the retrieved preference `summary`, and a
note of any candidate that was truth-blocked (never shown as a recommendation).
No resume edit is performed here; the user chooses, and application flows through
`inject-keywords` / `update-terminology`. Offer `log-edit-feedback` to record the
outcome.
