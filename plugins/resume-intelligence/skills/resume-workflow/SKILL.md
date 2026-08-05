---
name: resume-workflow
description: >
  The end-to-end runbook for tailoring a resume to a job with resume-intelligence.
  Sequences the single-purpose skills in the one obvious order — ingest → check →
  (optionally) improve → (optionally) second-agent review → validate truth →
  re-check for deltas → export — and names
  the gate (what must exist) for each step. This is a GUIDE: it points at the other
  skills, it does not call tools itself.
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
optional, advice-only **review-tailored-resume** step (step 5 below) is available.
**Offer it at most once per session** — and only after a tailored resume exists.
The guard is a presence marker at `resume-kit/.cache/review-offered`: once you have
offered the review (whether the user accepts or declines), write that marker; before
offering again, check for it and stay silent if it exists. The review is always
opt-in and never auto-runs.

## Steps

1. **Ingest the resume** — run **resume-to-json**.
   gate: a source resume file (PDF/DOCX/MD/text). It orchestrates the gated
   pipeline: `resume-tool init` (if needed) → `resume-tool extract-text <source>`
   (deterministic, no LLM) → a confined interpretation subagent maps the extracted
   text into `ResumeDocument` JSON → `resume-tool validate-faithfulness --source
   <source> --json <candidate>` is the **blocking HARD GATE** (non-zero exit on
   drift; loops the subagent once on failure, then surfaces to the user) →
   on pass, writes `resume-kit/resumes/<name>-original.json` and records
   `active_resume` + source via `resume-tool set-active` (never hand-edits
   `config.json`).

2. **Ingest the job** — run **job-to-json**.
   gate: the job posting (text/URL/file). For file inputs it runs
   `resume-tool extract-text <file>`; pasted text / URL content skips extraction.
   A confined interpretation subagent maps the text into `JobDescription` JSON
   (structured `requirements`/`keywords`), then it records `active_job` (+ source
   for files) via `resume-tool set-active --job ... [--job-source ...]`.
   Note: `validate-faithfulness` targets `ResumeDocument`, so it does **not** gate
   jobs — job faithfulness is enforced by the skill's prose extraction gates. Writes
   `resume-kit/jobs/<name>-original.json` and sets `active_job`.

3. **Check the resume** — run all three (they are independent):
   - **check-ats-structure** — gate: `active_resume` JSON.
   - **check-keyword-match** — gate: `active_resume` + `active_job` JSON. Uses the
     synonym alias index (`alias_file`) when present to match variant terms.
   - **identify-resume-gaps** — gate: `active_resume` + `active_job` JSON.
   Record the baseline scores so step 6 can show deltas.

4. **Improve** *(only what steps 3 surfaced)*:
   - **inject-keywords** — gate: `active_resume` + `active_job` + the
     keyword-match/gap findings. Produces `ChangeProposal` records for
     missing-but-true keywords.
   - **update-terminology** — gate: `active_resume` + `active_job` + the synonym
     alias index (`alias_file`). Produces `ChangeProposal` records for wording
     swaps the resume already satisfies.

   The sanctioned write path is the edit-session loop, not direct JSON edits:
   ask the mode prompt (`interactive`, `review_at_end`, or `auto`) →
   `resume-tool review-edits open` / `open-edit-session` →
   `resume-tool review-edits prompt` / `session-prompt` →
   `resume-tool review-edits decide` / `decide-change` for every change,
   offering the `EditFeedbackReasonCode` enum on `reject` or `edit` →
   `resume-tool review-edits commit` / `commit-session` as the hard write gate →
   **validate-resume-truth**. Direct hand-editing of the working resume is
   unsupported unless followed by `resume-tool review-edits reconcile` /
   `reconcile-session`.

   When several truthful candidates are available, run **rank-edits** first via
   `rank-edit-candidates` / `edit_candidates_rank` (passing `alias_file`) and
   present the ranked reasons before opening the session. Once the user decides
   or edits a proposal, record the outcome through **log-edit-feedback** via
   `record-edit-feedback` / `edit_feedback_record`; this is part of the
   orchestrated loop's learning path, not a prose-only afterthought. **LLM
   auto-rewrite is disabled — there is no skill path that bulk-runs
   `align-resume`.**

5. **Second-agent review** *(optional — advice-only)* — run
   **review-tailored-resume**.
   gate: the **new** tailored resume JSON + the **original** resume JSON + the
   **job** JSON (all three must exist; this step only makes sense after tailoring).
   Dispatches a subagent to critique the tailored-vs-original-vs-job triple and
   writes **advice-only** findings to `resume-kit/review/<session>.md`. It never
   edits the resume and never auto-runs — the user opts in. This step is **offered
   at most once per session**, guarded by the `resume-kit/.cache/review-offered`
   marker (see above); skipping it does not affect the rest of the flow.

6. **Validate truth** — run **validate-resume-truth**.
   gate: the (improved) resume JSON + `CandidateEvidence` (build it with
   **build-candidate-evidence**, gate: resume JSON). Any unsupported or
   contradicted claim must be fixed before proceeding — never ship fabrications.

7. **Re-check for deltas** — re-run **check-ats-structure**,
   **check-keyword-match**, and **identify-resume-gaps** on the improved resume.
   gate: the improved resume JSON + `active_job`. Compare against the step-3
   baseline to confirm the changes actually helped.

8. **Export** — run **export-resume**.
   gate: the final resume JSON. Produces the PDF/DOCX artifact to submit.

## Supporting / maintenance

- **manage-synonyms** *(as needed)* — grows the alias index consumed by
  **check-keyword-match** and **update-terminology** via `alias_file`. Run it when
  a legitimate term is being missed because of naming variants.
- **compare-resume-versions** / **select-best-resume** *(optional)* — when you
  maintain multiple variants: compare two versions, or pick the best of several,
  against `active_job`.
