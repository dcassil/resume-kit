---
name: tailor-resume
description: >
  Job-specific tailoring over a prepared resume, active job, and durable
  learning/evidence. Runs the truth-gated scoring, improvement, validation, and
  re-scoring loop after Flow 1 and Flow 2, then stops before perfect/export.
  Best run in a subagent.
---

# tailor-resume - reusable Flow 3 job tailoring

Flow 3 runs after **prepare-base-resume** has produced the prepared
`refine`/canonical resume and seeded durable learning, and after **ingest-job**
has set `active_job` and grown the alias file for this job. It consumes those
prepared artifacts; it does not go back to the raw source resume.

The output is a tailored working resume under `resume-kit/working/`, written
only by the code-owned edit-session commit gate. This flow is safe to run
repeatedly per job as new evidence, aliases, or user decisions become available.

## Prerequisites

Run the shared **Prerequisites gate** -
[`../_shared/prerequisites.md`](../_shared/prerequisites.md).

- **Required prepared resume:** a `refine`/canonical `ResumeDocument` output
  from **prepare-base-resume**, or a recorded override that explicitly permits
  using another canonical resume artifact.
- **Required active job:** `active_job` in `resume-kit/config.json`, normally
  written by **ingest-job**.
- **Proof source for full injectability classification:** use at least one of:
  - a **distinct master resume** from the prepared baseline lineage described in
    [`../_shared/config-pointers.md`](../_shared/config-pointers.md).
  - **confirmed Flow 1 learning/evidence**, normally
    `resume-kit/learning/candidate-evidence.json`, `evidence_file`, or the
    configured `active_evidence`, so truthful additions can be proved.
- **Alias file:** use `config.json`'s `alias_file` when present, normally
  `resume-kit/learning/synonyms.json` from **ingest-job**. If absent, scoring
  runs with the seed lexicon only.
- **If the prepared resume is missing:** STOP and run **prepare-base-resume**
  first. Do not tailor against an original-only resume unless the user has
  recorded the override.
- **If `active_job` is missing:** STOP and run **ingest-job** first.
- **If both proof sources are missing:** continue only if the caller explicitly
  accepts **keyword-only gap classification**. In that degraded mode
  **check-gaps** can list missing job keywords, but it cannot responsibly
  distinguish `injectable_keywords` from `non_injectable_keywords`; do not
  present non-injectable labels as a factual claim about the candidate's
  abilities.

## Injectability proof contract

Flow 3 uses the same proof contract as
[`check-gaps`](../check-gaps/SKILL.md): `injectable_keywords` are missing from
the tailored resume but proved by a master-equivalent proof surface. That proof
surface may include a distinct master resume and/or confirmed Flow 1
learning-evidence. These are two inputs to one standard, not two different
standards.

Flow 1 learning/evidence can prove that a candidate genuinely has a skill or
claim, including one absent from both the tailored and master resumes. It is
proof input only: every resume edit still passes the existing edit-session,
commit, and truth gates. Never auto-insert a keyword just because evidence
exists.

## The walkthrough

1. **First scoring.** Run **check-keywords** and **check-gaps** against the
   prepared resume, active job, and available injectability proof source. Pass
   `alias_file` when present so baseline scoring honors confirmed terminology
   learning. Record these results as the before scores for later deltas. If the
   proof source is absent by explicit override, label the gap result
   **keyword-only gap classification**.

2. **Route truthful improvements.** Use only the improvements surfaced by the
   first scoring:
   - **update-keywords** for missing-but-true keywords that the prepared resume
     lacks but a distinct master resume or confirmed Flow 1 learning-evidence
     proves.
   - **update-terminology** for wording swaps where the prepared resume already
     satisfies a job keyword under a different surface term.
   - **rank-changes** first when several truthful candidates are available and
     the user wants the strongest changes presented in order.

   Drive all proposed changes through the shared change-application runbook:
   [`../_shared/apply-changes.md`](../_shared/apply-changes.md). That runbook
   owns mode selection, per-change decisions, `commit-session`, `validate-facts`,
   learning, and re-scoring. Direct JSON edits are unsupported unless the user
   intentionally edited out of band and the session is recovered through
   `resume-tool review-edits reconcile` / `edit_session_reconcile` /
   `reconcile-session`.

3. **Validate after committed changes.** After the edit-session commit writes a
   `working_path`, run **validate-facts** against that tailored resume and the
   available evidence. Unsupported or contradicted claims must be resolved before
   this flow reports success.

4. **Re-run scoring and report deltas.** Run **check-keywords** and
   **check-gaps** again on the tailored working resume, honoring `alias_file`
   when present. Compare the second scores to the first scores and report the
   keyword, gap, and overall deltas.

5. **Offer review-resume, advice only.** After a tailored working resume exists,
   optionally offer **review-resume**. It is advice-only: it critiques the
   tailored resume against the original resume and active job, writes findings
   under `resume-kit/review/`, and never edits. If the user accepts any advice,
   route resulting changes back through **update-keywords** /
   **update-terminology** and the shared apply runbook.

6. **Offer the missing-requirements interview when still low.** If the second
   scoring leaves `overall` below the configured `interview_threshold`
   (`config.json`, default 70), or any required requirement is still uncovered,
   surface that fact and optionally run **interview-missing-job-description**.
   The interview elicits grounding facts, persists confirmed evidence, re-runs
   **check-gaps** so newly proved terms become injectable, and routes every edit
   through **update-keywords** plus the shared apply runbook. A bare "yes" never
   writes a keyword.

## How to invoke

**Scoring**

```bash
resume-tool match --resume <refine-or-working.json> --job <job.json> [--alias-file <path>]
resume-tool identify-gaps --job <job.json> \
    --tailored <refine-or-working.json> --master <master.json> \
    [--alias-file <path>]
```

MCP tools: `resume_check_job_match`, `resume_identify_gaps`.

**Improvement candidates**

```bash
resume-tool identify-gaps --job <job.json> \
    --tailored <resume.json> --master <master.json> \
    [--alias-file <path>]
resume-tool suggest-terminology --resume <resume.json> --job <job.json> [--alias-file <path>]
resume-tool rank-edit-candidates --candidates <candidates.json> [--alias-file <path>]
```

MCP tools: `resume_identify_gaps`, `resume_suggest_terminology`,
`edit_candidates_rank`.

**Apply and validate**

```bash
resume-tool review-edits open --mode <interactive|review_at_end|auto> --changes <changes.json> --evidence <evidence.json>
resume-tool review-edits prompt
resume-tool review-edits decide --path <path> --action <approve|reject|edit|skip>
resume-tool review-edits commit
resume-tool review-edits reconcile
resume-tool validate-truth --resume <working.json> --evidence <evidence.json>
```

MCP tools: `edit_session_open`, `edit_session_prompt`,
`edit_session_decide`, `edit_session_commit`, `edit_session_reconcile`,
`resume_validate_truth`.

**Optional interview support**

```bash
resume-tool requirement-answer --query-key <requirement_key> --output json
resume-tool add-evidence --confirmed --content "<grounding fact>" --kind user_statement --tag <term> --update-active
resume-tool requirement-answer --answer <answer.json>
```

MCP tools: `mcp__resume-kit__requirement_answer_record`,
`mcp__resume-kit__candidate_evidence_add`.

**review-resume** is agent-driven and advice-only; it has no single CLI/MCP
surface.

## Output

Return the tailored `working_path`, the first and second scoring results, the
delta, the edit-session id, committed changes, rejected/skipped changes with
reason codes when supplied, validation results, grown aliases, and any optional
review/interview outcome.

This flow writes a tailored working resume and does **not** run **perfect** or
**export-resume**. Those belong to Flow 4 `finalize-resume`.
