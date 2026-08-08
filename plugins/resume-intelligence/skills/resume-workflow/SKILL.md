---
name: resume-workflow
description: >
  The end-to-end runbook for tailoring a resume to a job with resume-intelligence.
  Sequences the single-purpose skills in the one obvious order — ingest →
  baseline the resume (base → structure → refine, job-independent, REQUIRED before
  tailoring) → check against the job → (optionally) improve → (optionally)
  second-agent review → validate truth → re-check for deltas → perfect fit →
  export — and names
  the gate (what must exist) for each step, including that all job tailoring is
  gated behind a `refine` version (or a recorded override). This is a GUIDE: it
  points at the other skills, it does not call tools itself.
---

# resume-workflow — the canonical tailoring flow

Use this when you need to take a resume and a job posting and produce a tailored,
truthful, ATS-ready resume. Each step below names the **skill** to run and its
**gate** (what must already exist). Steps marked *(optional)* are skipped unless
the checks/user call for them. Every consuming skill also runs its own
[Prerequisites gate](../_shared/prerequisites.md); this guide is the order those
skills fit together.

All state lives under `resume-kit/` — `config.json` tracks `active_resume` and
`active_job`; `learning/` accumulates per-skill hints. Run the ingest conversions
in **subagents** so large document text stays out of the main context.

**Once-per-session review offer.** When a session starts in an initialized
`resume-kit/` working dir, the SessionStart hook reminds the agent that the
optional, advice-only **review-resume** step (step 6 below) is available.
**Offer it at most once per session** — and only after a tailored resume exists.
The guard is a presence marker at `resume-kit/.cache/review-offered`: once you have
offered the review (whether the user accepts or declines), write that marker; before
offering again, check for it and stay silent if it exists. The review is always
opt-in and never auto-runs.

## Steps

1. **Ingest the resume** — run **parse-resume**.
   gate: a source resume file (PDF/DOCX/MD/text). It orchestrates the gated
   pipeline: `resume-tool init` (if needed) → `resume-tool extract-text <source>`
   (deterministic, no LLM) → a confined interpretation subagent maps the extracted
   text into `ResumeDocument` JSON → `resume-tool validate-faithfulness --source
   <source> --json <candidate>` is the **blocking HARD GATE** (non-zero exit on
   drift; loops the subagent once on failure, then surfaces to the user) →
   on pass, writes `resume-kit/resumes/<name>-original.json` and records
   `active_resume` + source via `resume-tool set-active` (never hand-edits
   `config.json`).

2. **Baseline the resume** *(job-independent — REQUIRED before any tailoring)* —
   get the resume itself into good shape before a job enters the picture. Run in
   order:
   - **update-structure** — gate: a faithful `original` (`active_resume`). Runs
     the structural check + the auto-safe `base` fix behind the claim-preservation
     gate → writes `<name>-base.json`.
   - **update-shape** — gate: `base` exists. Runs deterministic shape analysis
     and the non-destructive canonical section pass behind the content-ledger and
     cross-section claim gates → writes `<name>-structure.json` only when those
     gates pass. It does no wording change, no budget/trim, and defers ambiguous
     section mappings for a user decision.
   - **check-best-practices** — gate: `structure` exists (or `base` with a
     recorded shape-pass override). Scores the structurally canonical resume and
     classifies findings `auto_suggestible` vs `needs_user_input` (read-only).
   - **update-refine** — gate: `structure` (or recorded override) + the
     best-practices report.
     Auto-applies truthful rewrites, elicits the user's real facts for
     `needs_user_input` items, and writes `<name>-refine.json` behind the
     claim-preservation gate. **`refine` becomes the default resume for all
     tailoring below** (formerly called `standard`).
   - **check-ats-view** *(read-only, optional)* — gate: any `ResumeDocument`
     (normally `refine`). Shows "what the ATS sees" — detected sections,
     extracted entities + years-of-experience, and the zoned keyword breakdown —
     so the user can confirm the parsed view before tailoring. Job-independent;
     never edits the resume and carries the standing note that a strong ATS match
     does not guarantee recruiter advancement.

   **Override:** if the user explicitly declines baselining, **record that
   override** (state it and note it in the session/config) so the tailoring gate
   below is satisfied; tailoring then runs on the active resume at the user's
   stated choice. Baselining is job-independent, so it can (and should) run before
   the job is ingested.

3. **Ingest the job** — run **parse-job**.
   gate: the job posting (text/URL/file). For file inputs it runs
   `resume-tool extract-text <file>`; pasted text / URL content skips extraction.
   A confined interpretation subagent maps the text into `JobDescription` JSON
   (structured `requirements`/`keywords`), then it records `active_job` (+ source
   for files) via `resume-tool set-active --job ... [--job-source ...]`.
   Note: `validate-faithfulness` targets `ResumeDocument`, so it does **not** gate
   jobs — job faithfulness is enforced by the skill's prose extraction gates. Writes
   `resume-kit/jobs/<name>-original.json` and sets `active_job`.

4. **Check against the job** *(tailoring — gated on `refine`)* — run:
   - **check-keywords** — gate: **`refine` present (or a recorded override)** +
     `active_job`. Runs against the `refine` resume; uses the synonym alias
     index (`alias_file`) when present to match variant terms.
   - **check-gaps** — gate: **`refine` (or override)** + `active_job`.

   The structural check already ran in baselining (**update-structure**), so it is
   not repeated here. Record the baseline scores so the re-check step can show
   deltas.

5. **Improve** *(tailoring — gated on `refine`; only what step 4 surfaced)*:
   - **update-keywords** — gate: **`refine` (or override)** + `active_job` + the
     keyword-match/gap findings. Produces `ChangeProposal` records for
     missing-but-true keywords.
   - **update-terminology** — gate: **`refine` (or override)** + `active_job` +
     the synonym alias index (`alias_file`). Produces `ChangeProposal` records for
     wording swaps the resume already satisfies.

   Both skills build their `ChangeProposal` records and then drive them through
   the shared change-application runbook
   [`../_shared/apply-changes.md`](../_shared/apply-changes.md): mode prompt →
   `open` → `prompt`/`decide` for every change (offering the
   `EditFeedbackReasonCode` enum on `reject`/`edit`) → `commit-session` hard write
   gate → **validate-facts** → re-score. Direct hand-editing of the working resume
   is unsupported unless followed by `resume-tool review-edits reconcile` /
   `reconcile-session`.

   When several truthful candidates are available, run **rank-changes** first via
   `rank-edit-candidates` / `edit_candidates_rank` (passing `alias_file`) and
   present the ranked reasons before opening the session. Decision outcomes are
   logged to **learn-change** automatically by the runbook's decide step. **LLM
   auto-rewrite is disabled — there is no skill path that bulk-runs
   `align-resume`.**

6. **Second-agent review** *(optional — advice-only)* — run
   **review-resume**.
   gate: the **new** tailored resume JSON + the **original** resume JSON + the
   **job** JSON (all three must exist; this step only makes sense after tailoring).
   Dispatches a subagent to critique the tailored-vs-original-vs-job triple and
   writes **advice-only** findings to `resume-kit/review/<session>.md`. It never
   edits the resume and never auto-runs — the user opts in. This step is **offered
   at most once per session**, guarded by the `resume-kit/.cache/review-offered`
   marker (see above); skipping it does not affect the rest of the flow.

7. **Validate truth** — run **validate-facts**.
   gate: the (improved) resume JSON + `CandidateEvidence` (build it with
   **extract-evidence**, gate: resume JSON). Any unsupported or
   contradicted claim must be fixed before proceeding — never ship fabrications.

8. **Re-check for deltas** — re-run **check-keywords** and **check-gaps** on the
   improved resume.
   gate: the improved resume JSON + `active_job`. Compare against the step-4
   baseline to confirm the changes actually helped.

9. **Perfect / fit** — run **perfect**.
   gate: the tailored resume JSON + `active_job`. Runs the job-aware budget fit,
   presents ranked trim/compression candidates, and commits only decision- or
   ranked-budget-accounted removals plus claim-gated compressions. Writes the
   final resume when the ledger gate passes.

10. **Export** — run **export-resume**.
   gate: the final resume JSON. Produces the PDF/DOCX artifact to submit. Export
   enforces the `max_pages` page HARD GATE, so fitting is not considered
   submission-ready until export passes.

## Supporting / maintenance

- **learn-terminology** *(as needed)* — grows the alias index consumed by
  **check-keywords** and **update-terminology** via `alias_file`. Run it when
  a legitimate term is being missed because of naming variants.
- **compare-versions** / **select-resume** *(optional)* — when you
  maintain multiple variants: compare two versions, or pick the best of several,
  against `active_job`.
