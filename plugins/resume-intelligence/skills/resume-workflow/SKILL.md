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

4. **Improve** *(optional — only what steps 3 surfaced)*:
   - **inject-keywords** *(optional)* — gate: `active_resume` + `active_job` +
     the keyword-match/gap findings. Add missing, truthful keywords.
   - **update-terminology** *(optional)* — gate: `active_resume` + the synonym
     alias index (`alias_file`). Align variant terms to the job's phrasing.
   Work on a mutable copy in `resume-kit/working/<session>/resume.json`; leave the
   `-original.json` pristine. **LLM auto-rewrite is disabled — there is no
   `align-resume`.** All edits are targeted, agent-made, and truthful.

   *Preference-learning loop (optional — no LLM):* when several truthful
   candidate edits are available for a pending improvement, you may
   (a) run **rank-edits** to rank the candidates against past outcomes + learned
   preferences and present the best one(s) with an explanation (it never
   auto-applies; the truth hard-block excludes any fabricated candidate),
   (b) apply the chosen candidate via the truth-gated improve skills above
   (`inject-keywords` / `update-terminology`), then
   (c) run **log-edit-feedback** to record the outcome so future rankings
   improve. This loop is entirely optional — skip it and the Improve phase still
   works exactly as described above.

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
