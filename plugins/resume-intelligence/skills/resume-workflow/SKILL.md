---
name: resume-workflow
description: >
  The end-to-end runbook for tailoring a resume to a job with resume-intelligence.
  Sequences the single-purpose skills in the one obvious order — ingest → check →
  (optionally) improve → validate truth → re-check for deltas → export — and names
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

## Steps

1. **Ingest the resume** — run **resume-to-json**.
   gate: a source resume file (PDF/DOCX/MD/text). Writes
   `resume-kit/resumes/<name>-original.json` and sets `active_resume`.

2. **Ingest the job** — run **job-to-json**.
   gate: the job posting (text/URL/file). Writes
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

5. **Validate truth** — run **validate-resume-truth**.
   gate: the (improved) resume JSON + `CandidateEvidence` (build it with
   **build-candidate-evidence**, gate: resume JSON). Any unsupported or
   contradicted claim must be fixed before proceeding — never ship fabrications.

6. **Re-check for deltas** — re-run **check-ats-structure**,
   **check-keyword-match**, and **identify-resume-gaps** on the improved resume.
   gate: the improved resume JSON + `active_job`. Compare against the step-3
   baseline to confirm the changes actually helped.

7. **Export** — run **export-resume**.
   gate: the final resume JSON. Produces the PDF/DOCX artifact to submit.

## Supporting / maintenance

- **manage-synonyms** *(as needed)* — grows the alias index consumed by
  **check-keyword-match** and **update-terminology** via `alias_file`. Run it when
  a legitimate term is being missed because of naming variants.
- **compare-resume-versions** / **select-best-resume** *(optional)* — when you
  maintain multiple variants: compare two versions, or pick the best of several,
  against `active_job`.
