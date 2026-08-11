---
name: check-gaps
description: >
  Check and produce ONLY the missing / injectable keyword list between a
  tailored resume, a proof surface, and a job description — which job keywords
  are missing from the tailored resume, which can be proved from a distinct
  master resume and/or confirmed Flow 1 learning-evidence (injectable), and
  which are not proved by either source (non-injectable). No coverage percentage
  focus, no composite score. No LLM required.
---

> **Renamed:** `check-gaps` was `identify-resume-gaps` before v1.0.0 (see RIT-A-0005).


## Prerequisites

Run the shared **Prerequisites gate** first — see
[`_shared/prerequisites.md`](../_shared/prerequisites.md).

- **Required inputs:**
  - a **`JobDescription` JSON** — the `active_job` pointer in
    `resume-kit/config.json` (or an explicit job JSON path the caller passes).
  - a **tailored `ResumeDocument` JSON** — the `active_resume` pointer (or an
    explicit resume JSON path the caller passes) — the resume being evaluated.
- **Proof source for full injectability classification:** use at least one of:
  - a **distinct master `ResumeDocument` JSON** — the full master resume used
    to decide which missing job keywords are already supported outside the
    tailored resume. Prefer an explicit master path; where applicable fall back
    to the prepared baseline lineage described in
    [`../_shared/config-pointers.md`](../_shared/config-pointers.md).
  - **confirmed Flow 1 learning-evidence** — normally
    `resume-kit/learning/candidate-evidence.json`, `evidence_file`, or the
    configured `active_evidence`, whose confirmed facts can prove additions the
    resume may truthfully make.
- **If any required input is missing** (no pointer, file absent, or a raw file
  where a canonical JSON is required): **STOP**. Do not guess and do not run on
  partial input. Name the upstream skill for the missing one:
  - Missing/unconverted tailored resume → run **`parse-resume`**.
  - Missing/unconverted job → run **`parse-job`**.
- **If no proof source is available:** continue only if the caller explicitly
  accepts **keyword-only gap classification**. Otherwise, obtain a distinct
  master with **`parse-resume`** or obtain confirmed learning-evidence with
  **`extract-evidence`** / the Flow 1 preparation skill that owns it.

Conversions are best run in **subagents** (large intermediate text stays out of
the main context); pass the saved JSON paths back here — they live under
`resume-kit/resumes/` and `resume-kit/jobs/`.

## Injectability proof contract

`injectable_keywords` means a keyword is missing from the tailored resume but is
proved by the same master-equivalent proof surface used by Flow 3
[`tailor-resume`](../tailor-resume/SKILL.md). That proof surface may include:

- a **distinct master resume**, where the keyword appears in the candidate's
  source-of-truth resume but not in the tailored resume.
- **confirmed Flow 1 learning-evidence**, where the keyword is absent from both
  resumes but the evidence content proves the candidate genuinely has it.

These are two inputs to one proof contract, not two different standards. Flow 1
learning-evidence can prove that an addition is true, but every resulting resume
edit still must pass the existing edit-session, commit, and truth gates.

If neither a distinct master resume nor confirmed Flow 1 learning-evidence is
available, label the result **keyword-only gap classification**. In that
degraded mode the skill can still list keywords missing from the tailored
resume, but it cannot responsibly distinguish `injectable_keywords` from
`non_injectable_keywords`; do not present non-injectable labels as a factual
claim about the candidate's abilities.

## Purpose

Produce a `KeywordGapAnalysis` showing which job keywords are missing from the
tailored resume, which can be added because the shared proof surface supports
them (injectable), and which are not proved by that surface (non-injectable).

## When to use

- To understand what keyword gaps exist and whether they are addressable before
  editing or mirroring terminology in the resume.
- When the user wants to see the missing / injectable keyword list without
  committing to any resume changes.

## Inputs

| Field | Type | Notes |
|---|---|---|
| `job` | `JobDescription` | The target job |
| `tailored` | `ResumeDocument` | The resume version being evaluated |
| `master` | `ResumeDocument` | The full master resume used by the current CLI/MCP surface to check injectability |

**Options** (`CapabilityOptions`)

| Option | Default | Effect |
|---|---|---|
| `strict` | false | Escalate advisory warnings to failures |

`no_llm` has no effect — this capability is always deterministic.

## How to invoke

**CLI**

```
resume-tool identify-gaps --job <job.json> \
    --tailored <tailored.json> --master <master.json> \
    [--output {json,text,md}] [--strict]
```

**MCP tool**: `resume_identify_gaps`

Input fields: `job`, `tailored`, `master`, `strict`.

## Output (`InterfaceResponse`)

| Field | Type | Notes |
|---|---|---|
| `data` | `KeywordGapAnalysis` | `current_match_percentage`, `injectable_keywords`, `non_injectable_keywords` |
| `warnings` | list | Advisory issues |
| `errors` | list | Failures |
| `requiresHumanInput` | bool | Always false |
| `questions` | list | Always empty |
| `provenance` | object | Source attribution |

## Honor the project synonym index

Read `resume-kit/config.json`'s `alias_file` (default
`resume-kit/learning/synonyms.json`) and pass it to this capability so the
grown, user-confirmed synonym index is honored: add `--alias-file <path>` on the
CLI, or set the `alias_file` field on the `resume_identify_gaps` MCP request. The
engine UNIONs the project file over the seed lexicon; scoring stays fully
deterministic (no LLM).

## After analysis: grow the synonym index (truth-gated)

After you report the gap analysis, for each missing job keyword that the resume
plausibly satisfies under a DIFFERENT surface term, run the shared
**`learn-terminology`** workflow: it applies the truthfulness gate (genuine
same-skill synonym only — NetSuite↔SuiteCommerce yes, React≈Vue never; never
alias to make an ABSENT skill score as present), asks the user to confirm, and
only then appends a justified `{canonical, alias, why}` entry to the alias file
so the next deterministic run matches it. Do not confuse this with
`non_injectable_keywords`: a genuinely absent skill is a real gap and must NOT be
aliased away. Never append silently; always report exactly what was added. See
the `learn-terminology` skill for the full workflow and file format.

## Gaps vs. terminology mirrors

A **gap** is a JD keyword absent from the resume — surface it here, never rewrite
it in. Distinct from a **terminology mirror**, where the resume already satisfies
the JD keyword under a different surface form (an alias hit); mirroring the
employer's exact wording is truthful and is handled by the **`update-terminology`**
skill. Keep the two apart: a real gap must NOT be aliased or mirrored away.

## Notes

- Fully deterministic.  No provider needed.
- `injectable_keywords` = keywords in the job but not in tailored, proved by a
  distinct master resume and/or confirmed Flow 1 learning-evidence (the
  alignment engine can propose them without inventing facts, subject to the
  existing truth gates).
- `non_injectable_keywords` = keywords in the job but not in tailored and not
  proved by either available proof source.
- Do not claim the user possesses non-injectable skills.
